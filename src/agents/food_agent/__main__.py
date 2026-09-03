import uvicorn
from config import get_food_agent_host, get_food_agent_port
from .app import create_food_agent_app

if __name__ == "__main__":
    app = create_food_agent_app()
    uvicorn.run(app, host=get_food_agent_host(), port=get_food_agent_port())
