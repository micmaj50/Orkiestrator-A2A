from langgraph.graph import StateGraph, START, END

from agents.state import GraphState, TaskStatus


# Agents the orchestrator is allowed to route work to. Keep this in sync with
# the conditional edges registered below.
ROUTABLE_AGENTS = {'gas_agent', 'food_agent'}


async def orchestrator_node(state: GraphState) -> dict:
    """Orchestrator node that decides which sub-agent to call next based on the current state"""

    # TODO: Implement logic to decide which sub-agent to call next based on the current state

    return {}


def route_from_orchestrator(state: GraphState) -> str:
    """Route to the next agent based on the orchestrator's tasks list.

    Returns the agent assigned to the first in-progress task, as long as it is a
    known routable agent. Anything unknown (or no pending work) falls through to
    the response synthesizer, so the graph never routes to an edge that does not
    exist.
    """

    for task in state.tasks:
        if (
            task.status == TaskStatus.IN_PROGRESS
            and task.assigned_agent in ROUTABLE_AGENTS
        ):
            return task.assigned_agent

    return 'response_synthesizer'


async def gas_agent_node(state: GraphState) -> dict:
    """Gas sub-agent node that handles gas-station tasks and returns its result"""

    # TODO: Implement logic to call the Gas sub-agent and return its result.
    #       Must mark the handled task as COMPLETED/FAILED to avoid looping.

    return {}


async def food_agent_node(state: GraphState) -> dict:
    """Food sub-agent node that handles food-point tasks and returns its result"""

    # TODO: Implement logic to call the Food sub-agent and return its result.
    #       Must mark the handled task as COMPLETED/FAILED to avoid looping.

    return {}


async def response_synthesizer_node(state: GraphState) -> dict:
    """Response synthesizer node that combines results from sub-agents and generates a final response"""

    # TODO: Implement logic to synthesize results from sub-agents and generate a final response

    return {}


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
