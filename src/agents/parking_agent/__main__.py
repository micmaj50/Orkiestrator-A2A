import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from config import get_parking_agent_host, get_parking_agent_port, get_parking_agent_url
from .agent_executor import ParkingAgentExecutor
from starlette.applications import Starlette


if __name__ == '__main__':
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

    # Connect incoming A2A requests to the executor and task store.
    request_handler = DefaultRequestHandler(
        agent_executor=ParkingAgentExecutor(),
        # The task_store is used to store and manage tasks
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    # Creating the routes for the A2A server
    # These routes handle the incoming requests from the clients
    # and the outgoing responses to the clients
    routes = []

    routes.extend(create_agent_card_routes(agent_card))

    routes.extend(create_jsonrpc_routes(request_handler, '/'))

    # Create a web app with the defined routes
    app = Starlette(routes=routes)
    uvicorn.run(app, host=get_parking_agent_host(), port=get_parking_agent_port())
