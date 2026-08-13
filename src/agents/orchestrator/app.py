from pathlib import Path
from starlette.applications import Starlette

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore

from utils.card_loader import load_agent_card
from config import get_orchestrator_url
from .agent_executor import OrchestratorExecutor


def create_orchestrator_app() -> Starlette:
    """Creates and returns the Starlette sub-application for the Orchestrator."""
    card_path = Path(__file__).parent / "card.json"
    agent_card = load_agent_card(card_path, agent_url=get_orchestrator_url())

    request_handler = DefaultRequestHandler(
        agent_executor=OrchestratorExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(request_handler, "/"))

    return Starlette(routes=routes)