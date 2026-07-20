from langgraph.graph import StateGraph, START, END

from src.agents.state import GraphState, TaskStatus


async def orchestrator_node(state: GraphState) -> dict:
    """Orchestrator node that decides which sub-agent to call next based on the current state"""

    # TODO: Implement logic to decide which sub-agent to call next based on the current state

    return {}


def route_from_orchestrator(state: GraphState) -> str:
    """Route to the next agent based on the orchestrator's tasks list"""
    
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent:
            return task.assigned_agent
        
    return 'response_synthesizer'


async def gas_agent_node(state: GraphState) -> dict:
    # TODO: Implement logic to call the Gas sub-agent and return its result

    return {}


async def food_agent_node(state: GraphState) -> dict:
    # TODO: Implement logic to call the Food sub-agent and return its result

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