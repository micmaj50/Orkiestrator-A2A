from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from config import get_parking_agent_url

# Define the abilities or functions that agent can perform.
skill = AgentSkill(
    id='find-parking-lots',
    name='Find Parking Lots and Spaces',
    description='Finds parking lots, garages, and parking spaces near the vehicle or a specified location.',
    input_modes=['text/plain'],
    output_modes=['text/plain'],
    tags=['parking', 'garage', 'vehicle', 'location'],
    examples=[
        'find parking near my current location',
        'where can I park near Wawel Castle in Krakow',
        'find a parking space within 2km',
    ],
)
# Publish metadata that A2A clients use to discover the agent
agent_card = AgentCard(
    name='Parking Agent',
    description='Sub-agent for finding parking options based on location constraints.',
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
            url=get_parking_agent_url(),
            protocol_version='1.0',
        )
    ],
    # The list of AgentSkill objects that this agent offers
    skills=[skill],
)
