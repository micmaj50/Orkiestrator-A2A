import os
from pathlib import Path
from dotenv import load_dotenv
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette
from utils.card_loader import load_agent_card
from config import get_weather_agent_host, get_weather_agent_port, get_weather_agent_url
from .agent_executor import (
    WeatherAgentExecutor,
    WeatherAgent,
    MockWeatherAgent
)

if __name__ == '__main__':
    load_dotenv()

    MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() == "true"
    
    card_path = Path(__file__).parent / "card.json"
    agent_card = load_agent_card(card_path, agent_url=get_weather_agent_url())

    if MOCK_MODE:
        print("Running WeatherAgent in MOCK_MODE")
        active_agent = MockWeatherAgent()
    else:
        print("Running WeatherAgent")
        active_agent = WeatherAgent()

    executor = WeatherAgentExecutor(agent=active_agent)

    # Connect incoming A2A requests to the executor and task store.
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(request_handler, '/'))

    app = Starlette(routes=routes)
    uvicorn.run(app, host=get_weather_agent_host(), port=get_weather_agent_port())