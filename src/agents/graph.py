import multiprocess
from a2a.types import AgentCard, TaskState
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langfuse import observe
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from qdrant_client import QdrantClient

from agents.orchestrator.delegator import Delegator
from agents.orchestrator.llm import Llm
from agents.orchestrator.task_division_verifier import TaskDivisionVerifier
from agents.registry import discover_agents
from agents.state import GraphState, WorkItem, WorkItemStatus
from agents.synthesizer import Synthesizer
from config import get_agent_url, get_max_tasks
from context.car import create_mock_car
from contracts.agent_request import AgentRequest
from utils.a2a_client import call_sub_agent
from utils.card_loader import load_agent_card
from utils.database import search_skill, upload_agents_cards

AGENT_NODE = 'agent_node'
SYNTHESIZER_NODE = 'response_synthesizer'
ASK_USER_NODE = 'ask_user_node'

llm: Llm | None = None
delegator: TaskDivisionVerifier | None = None
synthesizer = Synthesizer()
qdrant_client: QdrantClient | None = None
car = create_mock_car()
_sub_agent_cards: dict[str, AgentCard] | None = None

def agent_url(card: AgentCard) -> str:
    """Where the agent listens."""

    return str(card.supported_interfaces[0].url)

def _safe_del(self):
    try:
        self._stop()
    except Exception:
        pass

multiprocess.resource_tracker.ResourceTracker.__del__ = _safe_del # type: ignore


def _load_sub_agent_cards() -> dict[str, AgentCard]:
    cards = {}

    for definiton in discover_agents():
        if definiton.is_orchestrator:
            continue

        cards[definiton.key] = load_agent_card(definiton.card_path, agent_url=get_agent_url(definiton.key))

    return cards


def get_sub_agent_cards() -> dict[str, AgentCard]:
    """Load discovered sub-agent cards on first use and cache the result."""
    global _sub_agent_cards

    if _sub_agent_cards is None:
        _sub_agent_cards = _load_sub_agent_cards()

    return _sub_agent_cards


def get_qdrant_client() -> QdrantClient:
    global qdrant_client

    if qdrant_client is None:
        qdrant_client = QdrantClient(":memory:")
        upload_agents_cards(qdrant_client, get_sub_agent_cards())

    return qdrant_client


async def orchestrator_node(state: GraphState) -> dict:
    """Orchestrator node that asks the LLM (Delegator) which sub-agent(s) to call."""

    global llm, delegator
    client =  get_qdrant_client()
    if state.tasks:
        return {}

    if delegator is None:
        if llm is None:
            llm = Llm()

        base_delegator = Delegator(Llm=llm)
        delegator = TaskDivisionVerifier(delegator=base_delegator, llm=llm)

    raw = delegator.invoke(state, None)
    print(raw)
    if isinstance(raw, dict):
        items = raw.get('tasks', [])
    else:
        items = []

    max_tasks = get_max_tasks()
    dropped = False

    tasks: list[WorkItem] = []
    for index, item in enumerate(items, start=1):
        # The delegator can submit any number of tasks, so the fan-out is limited.
        if len(tasks) >= max_tasks:
            dropped = True
            break

        if not isinstance(item, dict):
            continue

        try:
            task_id = int(item.get('id'))
        except (TypeError, ValueError):
            task_id = index

        query = item.get('query', '')
        request = AgentRequest(user_input= str(state.user_input.content), task= query)
        context = request.select_context(car_context=car, llm=llm)

        agent = search_skill(client, query_text=str(query))

        if agent not in get_sub_agent_cards():
            tasks.append(
                WorkItem(
                    id=task_id,
                    assigned_agent=agent,
                    status=WorkItemStatus.FAILED,
                    result="No agent matched this part of the request."
                )
            )
            continue

        new_task = WorkItem(
                id=task_id,
                assigned_agent=agent,
                query=item.get('query'),
                context=context,
            )

        tasks.append(new_task)
    return {'tasks': tasks, 'tasks_dropped': dropped}


def route_from_orchestrator(state: GraphState) -> str:
    """Keep visiting the shared agent node while any task is still pending."""


    for task in state.tasks:
        print(task)
        if task.status == WorkItemStatus.CONTEXT:
            return ASK_USER_NODE
        if task.status == WorkItemStatus.IN_PROGRESS and task.assigned_agent in get_sub_agent_cards():
            return AGENT_NODE

    return SYNTHESIZER_NODE

@observe(
        name="delegate_to_sub_agent",
        capture_input=False,
        capture_output=False
)
async def agent_node(state: GraphState) -> dict:
    """
    The one node that serves every sub-agent: it takes the next pending task,
    looks its agent up in the registry, calls it over A2A and records the result.
    """

    cards = get_sub_agent_cards()

    for task in state.tasks:
        if task.status == WorkItemStatus.IN_PROGRESS and task.assigned_agent in cards:
            card = cards[task.assigned_agent]

            try:
                query = task.query or str(state.user_input.content)
                car_gps: dict = {}
                if task.context is not None:
                    query += task.context.get_context_for_query()
                    car_gps = task.context.get_location_metadata()
                task_state, text = await call_sub_agent(query, agent_url(card), metadata=car_gps)

                if task_state == TaskState.TASK_STATE_COMPLETED:
                    task.status = WorkItemStatus.COMPLETED
                elif task_state == TaskState.TASK_STATE_INPUT_REQUIRED:
                    task.status = WorkItemStatus.CONTEXT
                else:
                    task.status = WorkItemStatus.FAILED

                task.result = text

            except Exception as exc:
                task.status = WorkItemStatus.FAILED
                task.result = f'{card.name} call failed: {exc}'

            return {'tasks': state.tasks}

    return {}


async def ask_user_node(state: GraphState) -> dict:
    global llm
    if llm is None:
        llm = Llm()

    context_tasks = [t for t in state.tasks if t.status == WorkItemStatus.CONTEXT]
    if not context_tasks:
        return {}

    ask_prompt = PromptTemplate.from_template(
    "You have the following tasks that require additional information.\n"
    "Every line is a task, followed by what its agent said it was missing:\n{tasks_info}\n\n"
    "Prepare request asking the user to provide the missing details."
    )
    tasks_summary = "\n".join(f"({t.query}) {t.result or ''}" for t in context_tasks)

    question_to_user = llm(
        prompt=ask_prompt,
        inputs={"tasks_info": tasks_summary},
        asJSON=False,
        observation_name="ask_user_question"
    )


    user_response = interrupt(str(question_to_user))



    update_prompt = PromptTemplate.from_template(
        "The user provided additional information: '{user_response}'.\n"
        "Here are the tasks that require query refinement:\n{tasks_info}\n\n"
        "Update the query for these tasks so that they include the provided context.\n"
        "Return the result strictly as a JSON matching this format: {{\"updates\": [{{\"id\": 1, \"updated_query\": \"...\"}}]}}"
    )

    tasks_for_update = "\n".join(f"id={t.id}: {t.query}" for t in context_tasks)

    result_dict = llm(
        prompt=update_prompt,
        inputs={
            "user_response": str(user_response),
            "tasks_info": tasks_for_update
        },
        asJSON=True,
        observation_name="ask_user_query_update"
    )


    if isinstance(result_dict, dict) and "updates" in result_dict:
        updates_map = {item["id"]: item["updated_query"] for item in result_dict["updates"] if "id" in item}

        for task in state.tasks:
            if task.id in updates_map:
                task.query = updates_map[task.id]
                task.status = WorkItemStatus.IN_PROGRESS
                task.result = None

    for task in context_tasks:
        if task.status == WorkItemStatus.CONTEXT:
            task.query = f"{task.query}. Additional context from the user: {user_response}"
            task.status = WorkItemStatus.IN_PROGRESS
            task.result = None

    return {
        "tasks": state.tasks,
        "messages": [
            AIMessage(content=str(question_to_user)),
            HumanMessage(content=str(user_response)),
        ],
    }


async def response_synthesizer_node(state: GraphState) -> dict:
    """
    Response synthesizer node that asks the LLM (Synthesizer) to combine the
    finished sub-agent results into a final message.
    """

    global llm

    if not any(task.result for task in state.tasks):
        message = "I couldn't handle that request. Please try again or ask for something else."
        return {'messages': [AIMessage(content=message)]}

    if llm is None:
        llm = Llm()

    final_text = synthesizer(state, llm, False)

    if not isinstance(final_text, str):
        final_text = str(final_text)

    return {'messages': [AIMessage(content=final_text)]}


graph_builder = StateGraph(GraphState)

graph_builder.add_node('orchestrator', orchestrator_node)
graph_builder.add_node(AGENT_NODE, agent_node)
graph_builder.add_node(SYNTHESIZER_NODE, response_synthesizer_node)
graph_builder.add_node(ASK_USER_NODE, ask_user_node)

graph_builder.add_edge(START, 'orchestrator')
graph_builder.add_conditional_edges('orchestrator', route_from_orchestrator, {
    AGENT_NODE: AGENT_NODE,
    SYNTHESIZER_NODE: SYNTHESIZER_NODE,
    ASK_USER_NODE: ASK_USER_NODE,
})

graph_builder.add_edge(AGENT_NODE, 'orchestrator')
graph_builder.add_edge(SYNTHESIZER_NODE, END)
graph_builder.add_edge(ASK_USER_NODE, AGENT_NODE)

graph = graph_builder.compile(checkpointer=InMemorySaver())
