import uvicorn
from pathlib import Path
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from utils.card_loader import load_agent_card
from config import get_bind_host, get_orchestrator_port, get_orchestrator_url
from .agent_executor import (
    OrchestratorExecutor,
)
from starlette.applications import Starlette


if __name__ == '__main__':
    card_path = Path(__file__).parent / "card.json"
    agent_card = load_agent_card(card_path, agent_url=get_orchestrator_url())

    request_handler = DefaultRequestHandler(
        # Agent executor handles the execution of the client requests
        agent_executor=OrchestratorExecutor(),
        # The task_store is used to store and manage tasks
        task_store=InMemoryTaskStore(),
        # Public agent card
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
    uvicorn.run(app, host=get_bind_host(), port=get_orchestrator_port())
