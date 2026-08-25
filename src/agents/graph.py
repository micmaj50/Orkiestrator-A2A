import multiprocess
from a2a.types import AgentCard
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from qdrant_client import QdrantClient

from agents.food_agent.agent_card import agent_card as food_agent_card
from agents.gas_agent.agent_card import agent_card as gas_agent_card
from agents.orchestrator.delegator import Delegator
from agents.orchestrator.llm import Llm
from agents.parking_agent.agent_card import agent_card as parking_agent_card
from agents.state import GraphState, Task, TaskStatus
from agents.synthesizer import Synthesizer
from agents.weather_agent.agent_card import agent_card as weather_agent_card
from utils.a2a_client import call_sub_agent
from utils.database import search_skill, upload_agents_from_file

AGENT_NODE = 'agent_node'
SYNTHESIZER_NODE = 'response_synthesizer'

llm: Llm | None = None
delegator: Delegator | None = None
synthesizer = Synthesizer()
qdrant_client: QdrantClient | None = None

def get_qdrant_client(path: str) -> QdrantClient:
    global qdrant_client
    if qdrant_client is None:
        qdrant_client = QdrantClient(":memory:")
        upload_agents_from_file(qdrant_client, path)
    return qdrant_client

AGENT_NODE = 'agent_node'
SYNTHESIZER_NODE = 'response_synthesizer'

def agent_url(card: AgentCard) -> str:
    """Where the agent listens."""

    return card.supported_interfaces[0].url



def _safe_del(self):
    try:
        self._stop()
    except Exception:
        pass

multiprocess.resource_tracker.ResourceTracker.__del__ = _safe_del # type: ignore

# The cards of the agents that are actually running, keyed by the agent key the
# delegator routes on.
SUB_AGENT_CARDS: dict[str, AgentCard] = {
    'gas_agent': gas_agent_card,
    'food_agent': food_agent_card,
    'parking_agent': parking_agent_card,
    'weather_agent': weather_agent_card,
}


async def orchestrator_node(state: GraphState) -> dict:
    """Orchestrator node that asks the LLM (Delegator) which sub-agent(s) to call."""

    global llm, delegator
    qdrant_client =  get_qdrant_client('database.json')
    if state.tasks:
        return {}

    if delegator is None:
        if llm is None:
            llm = Llm()
        delegator = Delegator(Llm=llm, AgentCard=SUB_AGENT_CARDS)


    raw = delegator.invoke(state, None)
    if isinstance(raw, dict):
        items = raw.get('tasks', [])
    else:
        items = []

    tasks: list[Task] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        agent = item.get('assigned_agent')

        try:
            task_id = int(item.get('id'))
        except (TypeError, ValueError):
            task_id = index


        query = item.get('query', '')
        matched_agents = search_skill(qdrant_client, query_text=str(query))
        agent = matched_agents

        new_task = Task(
                id=task_id,
                assigned_agent=agent,
                query=item.get('query'),
            )



        tasks.append(new_task)



    return {'tasks': tasks}


def route_from_orchestrator(state: GraphState) -> str:
    """Keep visiting the shared agent node while any task is still pending."""

    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent in SUB_AGENT_CARDS:
            return AGENT_NODE

    return SYNTHESIZER_NODE


async def agent_node(state: GraphState) -> dict:
    """
    The one node that serves every sub-agent: it takes the next pending task,
    looks its agent up in the registry, calls it over A2A and records the result.
    """

    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent in SUB_AGENT_CARDS:
            card = SUB_AGENT_CARDS[task.assigned_agent]

            try:
                query = task.query or str(state.user_input.content)
                result = await call_sub_agent(query, agent_url(card))

                task.status = TaskStatus.COMPLETED
                task.result = result

            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = f'{card.name} call failed: {exc}'

            output: dict = {'tasks': state.tasks}
            if task.result:
                # Publish the result on messages so the synthesizer can read it.
                output['messages'] = [AIMessage(content=task.result)]
            return output

    return {}


async def response_synthesizer_node(state: GraphState) -> dict:
    """
    Response synthesizer node that asks the LLM (Synthesizer) to combine the
    sub-agent only COMPLETED and FAILED task results into a final message.
    """

    global llm

    valid_tasks = [t for t in state.tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)]

    if not valid_tasks:
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

graph_builder.add_edge(START, 'orchestrator')
graph_builder.add_conditional_edges('orchestrator', route_from_orchestrator, {
    AGENT_NODE: AGENT_NODE,
    SYNTHESIZER_NODE: SYNTHESIZER_NODE,
})
graph_builder.add_edge(AGENT_NODE, 'orchestrator')
graph_builder.add_edge(SYNTHESIZER_NODE, END)

graph = graph_builder.compile()
