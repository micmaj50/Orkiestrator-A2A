import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from agents.weather_agent.agent_card import agent_card
from config import get_weather_agent_host, get_weather_agent_port

from .agent_executor import WeatherAgentExecutor

if __name__ == '__main__':
    # Connect incoming A2A requests to the executor and task store.
    request_handler = DefaultRequestHandler(
        agent_executor=WeatherAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(request_handler, '/'))

    app = Starlette(routes=routes)
    uvicorn.run(app, host=get_weather_agent_host(), port=get_weather_agent_port())