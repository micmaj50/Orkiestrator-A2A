from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)


# Define the abilities or functions that agent can perform.
skill = AgentSkill(
    id='find-restaurants-and-dining',
    name='Find Restaurants and Dining Options',
    description='Finds restaurants, cafes, and dining options near the vehicle or a specified location with optional cuisine filters.',
    input_modes=['text/plain'],
    output_modes=['text/plain'],
    tags=['food', 'restaurants', 'dining', 'cuisine'],
    examples=[
        'find some good sushi nearby',
        'I want to eat pizza in Radom',
        'find a restaurant near Berlin'
    ],
)

# Publish metadata that A2A clients (and the orchestrator) use to discover the agent.
agent_card = AgentCard(
    name='Food Agent',
    description='Sub-agent for finding food and drink options based on cuisine preference and location constraints.',
    version='1.0.0',
    # Default Media Types for the agent's interactions
    default_input_modes=['text/plain'],
    default_output_modes=['text/plain'],
    # Supported A2A features (like streaming or extended config)
    capabilities=AgentCapabilities(streaming=True, extended_agent_card=True),
    # Ordered list of endpoints and protocols where the service can be reached
    supported_interfaces=[
        AgentInterface(
            protocol_binding='JSONRPC',
            # Each agents exposes its A2A interface on a separate local port
            url='http://127.0.0.1:9997',
            protocol_version='1.0',
        )
    ],
    # The list of AgentSkill objects that this agent offers
    skills=[skill],
)
