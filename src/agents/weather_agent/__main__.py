import uvicorn
from config import get_weather_agent_host, get_weather_agent_port
from .app import create_weather_agent_app

if __name__ == "__main__":
    app = create_weather_agent_app()
    uvicorn.run(app, host=get_weather_agent_host(), port=get_weather_agent_port())
