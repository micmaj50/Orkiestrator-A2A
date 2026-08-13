import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from starlette.applications import Starlette
from starlette.routing import Mount

from agents.orchestrator.app import create_orchestrator_app
from agents.gas_agent.app import create_gas_agent_app
from agents.food_agent.app import create_food_agent_app
from agents.parking_agent.app import create_parking_agent_app
from agents.weather_agent.app import create_weather_agent_app

SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

app = Starlette(
    routes=[
        Mount("/gas", app=create_gas_agent_app()),
        Mount("/food", app=create_food_agent_app()),
        Mount("/orchestrator", app=create_orchestrator_app()),
        Mount("/parking", app=create_parking_agent_app()),
        Mount("/weather", app=create_weather_agent_app())
    ]
)

if __name__ == "__main__":
    print(f"Starting Agent Server at http://{SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)