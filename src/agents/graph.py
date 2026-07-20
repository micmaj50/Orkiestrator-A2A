from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END

from agents.state import GraphState, Task, TaskStatus
from utils.a2a_client import call_sub_agent


GAS_AGENT_URL = 'http://127.0.0.1:9998'
FOOD_AGENT_URL = 'http://127.0.0.1:9997'

ROUTABLE_AGENTS = {'gas_agent', 'food_agent'}

async def orchestrator_node(state: GraphState) -> dict:
    """
    Temporary orchestrator node that decides which sub-agent to call next based on the current state.
    In the future, this will be integrated with a more advanced orchestrator agent.
    """

    if state.tasks:
        return {}

    user_text = str(state.user_input.content).lower()

    tasks: list[Task] = []
    if 'gas' in user_text:
        tasks.append(
            Task(
                id='gas-1',
                name='Find gas stations',
                assigned_agent='gas_agent',
            )
        )
    if 'food' in user_text:
        tasks.append(
            Task(
                id='food-1',
                name='Find restaurants',
                assigned_agent='food_agent',
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
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent == 'gas_agent':
            try:
                result = await call_sub_agent(user_text, GAS_AGENT_URL)

                task.status = TaskStatus.COMPLETED
                task.result = result
                updated_tasks.append(task)

            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = f'Gas agent call failed: {exc}'
                updated_tasks.append(task)

        else:
            updated_tasks.append(task)

    return {'tasks': updated_tasks}


async def food_agent_node(state: GraphState) -> dict:
    """Food sub-agent node: calls the food agent over A2A and records the result."""

    user_text = str(state.user_input.content)

    updated_tasks: list[Task] = []
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent == 'food_agent':
            try:
                result = await call_sub_agent(user_text, FOOD_AGENT_URL)

                task.status = TaskStatus.COMPLETED
                task.result = result
                updated_tasks.append(task)

            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = f'Food agent call failed: {exc}'
                updated_tasks.append(task)
        else:
            updated_tasks.append(task)

    return {'tasks': updated_tasks}


async def response_synthesizer_node(state: GraphState) -> dict:
    """
    Temporary response synthesizer node that combines sub-agent results into a final message.
    In the future, this will be integrated with a more advanced response synthesis agent.
    """

    results = []
    for task in state.tasks:
        if task.result:
            results.append(task.result)

    if results:
        final_text = '\n\n'.join(results)
    else:
        final_text = "I couldn't handle that request. Try asking for gas stations or food."

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