import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from agents.gas_agent.agent_card import agent_card
from config import get_gas_agent_host, get_gas_agent_port

from .agent_executor import (
    GasStationAgentExecutor,  # type: ignore[import-untyped]
)

if __name__ == '__main__':
    # Connect incoming A2A requests to the executor and task store.
    request_handler = DefaultRequestHandler(
        agent_executor=GasStationAgentExecutor(),
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
    uvicorn.run(app, host=get_gas_agent_host(), port=get_gas_agent_port())
