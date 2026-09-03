from importlib import import_module

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from agents.registry import get_agent_definition
from config import get_agent_url
from utils.card_loader import load_agent_card


def create_agent_app(agent_name: str) -> Starlette:
    definition = get_agent_definition(agent_name)
    agent_card = load_agent_card(definition.card_path, agent_url=get_agent_url(definition.key))
    module = import_module(f"agents.{agent_name}.app")
    executor = module.create_executor()

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=agent_card
    )
    routes = [*create_agent_card_routes(agent_card), *create_jsonrpc_routes(request_handler, "/")]

    return Starlette(routes=routes)
