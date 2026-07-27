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

from config import get_food_agent_host, get_food_agent_port, get_food_agent_url
from .agent_executor import (
    FoodAgentExecutor,  # type: ignore[import-untyped]
)
from starlette.applications import Starlette


if __name__ == '__main__':
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

    # Publish metadata that A2A clients use to discover the agent
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
                url=get_food_agent_url(),
                protocol_version='1.0',
            )
        ],
        # The list of AgentSkill objects that this agent offers
        skills=[skill],
    )

    # Connect incoming A2A requests to the executor and task store.
    request_handler = DefaultRequestHandler(
        agent_executor=FoodAgentExecutor(),
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
    uvicorn.run(app, host=get_food_agent_host(), port=get_food_agent_port())
