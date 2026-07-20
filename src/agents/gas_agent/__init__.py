from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from config import get_gas_agent_url

# Define the abilities or functions that agent can perform.
skill = AgentSkill(
    id='find_closest_gas_station',
    name='Find Closest Gas Stations',
    description='Finds the nearest gas stations, using either the car location or a specified location.',
    input_modes=['text/plain'],
    output_modes=['text/plain'],
    tags=['gas-stations'],
    examples=['find the closest gas stations', 'find a gas station near Big Ben'],
)
# Publish metadata that A2A clients use to discover the agent
agent_card = AgentCard(
    name='Gas Station Agent',
    description='Sub-agent for geocoding and discovering nearby gas stations.',
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
            url=get_gas_agent_url(),
            protocol_version='1.0',
        )
    ],
    # The list of AgentSkill objects that this agent offers
    skills=[skill],
)