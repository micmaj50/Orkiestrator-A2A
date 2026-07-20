from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END

from agents.state import GraphState, Task, TaskStatus
from agents.orchestrator.Llm import Llm
from agents.orchestrator.Delegator import Delegator
from agents.synthesizer import Synthesizer
from agents.gas_agent import agent_card as gas_agent_card
from agents.food_agent import agent_card as food_agent_card
from utils.a2a_client import call_sub_agent


GAS_AGENT_URL = 'http://127.0.0.1:9998'
FOOD_AGENT_URL = 'http://127.0.0.1:9997'

# Routing keys mapped to the sub-agent cards defined in each agent's package.
SUB_AGENT_CARDS = {
    'gas_agent': gas_agent_card,
    'food_agent': food_agent_card,
}
ROUTABLE_AGENTS = set(SUB_AGENT_CARDS)

# LLM-backed components are created lazily on first use so importing / compiling
# the graph does not require an OpenAI API key (only running it does).
llm: Llm | None = None
delegator: Delegator | None = None
synthesizer = Synthesizer()


async def orchestrator_node(state: GraphState) -> dict:
    """Orchestrator node that asks the LLM (Delegator) which sub-agent(s) to call."""

    global llm, delegator

    if state.tasks:
        return {}

    if delegator is None:
        llm = llm or Llm()
        delegator = Delegator(Llm=llm, AgentCards=SUB_AGENT_CARDS)

    raw = delegator.invoke(state, None)
    items = raw.get('tasks', []) if isinstance(raw, dict) else []

    tasks: list[Task] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        agent = item.get('assigned_agent')
        if agent not in ROUTABLE_AGENTS:
            continue
        tasks.append(
            Task(
                id=str(item.get('id') or f'{agent}-{index}'),
                name=str(item.get('name') or agent),
                assigned_agent=agent,
            )
        )

    return {'tasks': tasks}


def route_from_orchestrator(state: GraphState) -> str:
    """Route to the next agent based on the orchestrator's tasks list"""

    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent in ROUTABLE_AGENTS:
            return task.assigned_agent

    return 'response_synthesizer'


async def gas_agent_node(state: GraphState) -> dict:
    """Gas sub-agent node: calls the gas station agent over A2A and records the result."""

    user_text = str(state.user_input.content)

    updated_tasks: list[Task] = []
    produced: str | None = None
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent == 'gas_agent':
            try:
                result = await call_sub_agent(user_text, GAS_AGENT_URL)

                task.status = TaskStatus.COMPLETED
                task.result = result

            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = f'Gas agent call failed: {exc}'

            produced = task.result
            updated_tasks.append(task)

        else:
            updated_tasks.append(task)

    output: dict = {'tasks': updated_tasks}
    if produced:
        # Publish the result on messages so the synthesizer can read it.
        output['messages'] = [AIMessage(content=produced)]
    return output


async def food_agent_node(state: GraphState) -> dict:
    """Food sub-agent node: calls the food agent over A2A and records the result."""

    user_text = str(state.user_input.content)

    updated_tasks: list[Task] = []
    produced: str | None = None
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent == 'food_agent':
            try:
                result = await call_sub_agent(user_text, FOOD_AGENT_URL)

                task.status = TaskStatus.COMPLETED
                task.result = result

            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = f'Food agent call failed: {exc}'

            produced = task.result
            updated_tasks.append(task)

        else:
            updated_tasks.append(task)

    output: dict = {'tasks': updated_tasks}
    if produced:
        # Publish the result on messages so the synthesizer can read it.
        output['messages'] = [AIMessage(content=produced)]
    return output


async def response_synthesizer_node(state: GraphState) -> dict:
    """Response synthesizer node that asks the LLM (Synthesizer) to combine the
    sub-agent results into a final message."""

    global llm

    has_results = any(task.result for task in state.tasks)
    if not has_results:
        return {'messages': [AIMessage(
            content="I couldn't handle that request. Try asking for gas stations or food."
        )]}

    llm = llm or Llm()
    final_text = synthesizer(state, llm, False)
    if not isinstance(final_text, str):
        final_text = str(final_text)

    return {'messages': [AIMessage(content=final_text)]}


graph_builder = StateGraph(GraphState)

graph_builder.add_node('orchestrator', orchestrator_node)
graph_builder.add_node('gas_agent', gas_agent_node)
graph_builder.add_node('food_agent', food_agent_node)
graph_builder.add_node('response_synthesizer', response_synthesizer_node)

graph_builder.add_edge(START, 'orchestrator')
graph_builder.add_conditional_edges('orchestrator', route_from_orchestrator, {
    'gas_agent': 'gas_agent',
    'food_agent': 'food_agent',
    'response_synthesizer': 'response_synthesizer'
})
graph_builder.add_edge('gas_agent', 'orchestrator')
graph_builder.add_edge('food_agent', 'orchestrator')
graph_builder.add_edge('response_synthesizer', END)

graph = graph_builder.compile()
