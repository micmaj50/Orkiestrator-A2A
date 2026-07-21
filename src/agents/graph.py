from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END

from agents.state import GraphState, Task, TaskStatus
from agents.orchestrator.Llm import Llm
from agents.orchestrator.Delegator import Delegator
from agents.synthesizer import Synthesizer
from agents.gas_agent import agent_card as gas_agent_card
from agents.food_agent import agent_card as food_agent_card
from utils.a2a_client import call_sub_agent

from config import get_food_agent_url, get_gas_agent_url


SUB_AGENT_CARDS = {
    'gas_agent': gas_agent_card,
    'food_agent': food_agent_card,
}
ROUTABLE_AGENTS = set(SUB_AGENT_CARDS)

llm: Llm | None = None
delegator: Delegator | None = None
synthesizer = Synthesizer()


async def orchestrator_node(state: GraphState) -> dict:
    """Orchestrator node that asks the LLM (Delegator) which sub-agent(s) to call."""

    global llm, delegator

    if state.tasks:
        return {}

    if delegator is None:
        if llm is None:
            llm = Llm()
        delegator = Delegator(Llm=llm, AgentCards=SUB_AGENT_CARDS)

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
        if agent not in ROUTABLE_AGENTS:
            continue

        try:
            task_id = item.get('id')
        except (TypeError, ValueError):
            task_id = index

        new_task = Task(
            id=task_id,
            assigned_agent=agent,
            query=item.get('query'),
        )
        tasks.append(new_task)

    return {'tasks': tasks}


def route_from_orchestrator(state: GraphState) -> str:
    """Route to the next agent based on the orchestrator's tasks list"""
    
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent in ROUTABLE_AGENTS:
            return task.assigned_agent
        
    return 'response_synthesizer'


async def gas_agent_node(state: GraphState) -> dict:
    """Gas sub-agent node: calls the gas station agent over A2A and records the result."""

    updated_tasks: list[Task] = []
    produced: str | None = None
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent == 'gas_agent':
            try:
                query = task.query or str(state.user_input.content)
                result = await call_sub_agent(query, get_gas_agent_url())

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
        output['messages'] = [AIMessage(content=produced)]
    return output


async def food_agent_node(state: GraphState) -> dict:
    """Food sub-agent node: calls the food agent over A2A and records the result."""

    updated_tasks: list[Task] = []
    produced: str | None = None
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent == 'food_agent':
            try:
                # Prefer the task-specific query; fall back to the full user input.
                query = task.query or str(state.user_input.content)
                result = await call_sub_agent(query, get_food_agent_url())

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
    """
    Response synthesizer node that asks the LLM (Synthesizer) to combine the
    sub-agent results into a final message.
    """

    global llm

    has_results = False
    for task in state.tasks:
        if task.result:
            has_results = True
            break

    if not has_results:
        message = "I couldn't handle that request. Try asking for gas stations or food."
        return {'messages': [AIMessage(content=message)]}
    
    if llm is None:
        llm = Llm()
    
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