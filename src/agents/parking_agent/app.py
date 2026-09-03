import os
from pathlib import Path
from dotenv import load_dotenv
from starlette.applications import Starlette

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore

from utils.card_loader import load_agent_card
from config import get_parking_agent_url
from .agent_executor import (
    ParkingAgentExecutor,
    ParkingAgent,
    MockParkingAgent,
)

load_dotenv()


def create_parking_agent_app() -> Starlette:
    """Creates and returns the Starlette sub-application for the Parking Agent."""
    mock_mode = os.environ.get("MOCK_MODE", "false").lower() == "true"

    card_path = Path(__file__).parent / "card.json"
    agent_card = load_agent_card(card_path, agent_url=get_parking_agent_url())

    if mock_mode:
        active_agent = MockParkingAgent()
    else:
        active_agent = ParkingAgent()

    executor = ParkingAgentExecutor(agent=active_agent)

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(request_handler, "/"))

    return Starlette(routes=routes)