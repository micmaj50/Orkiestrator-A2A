import os
from dotenv import load_dotenv
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from agents.food_agent.agent_card import agent_card
from config import get_food_agent_host, get_food_agent_port

from .agent_executor import (
    FoodAgentExecutor,  # type: ignore[import-untyped]
    FoodAgent,
    MockFoodAgent
)

if __name__ == '__main__':
    load_dotenv()

    MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"

    if MOCK_MODE:
        print("Running FoodAgent in MOCK_MODE")
        active_agent = MockFoodAgent()
    else:
        print("Running FoodAgent")
        active_agent = FoodAgent()

    executor = FoodAgentExecutor(agent=active_agent)

    # Connect incoming A2A requests to the executor and task store.
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
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
