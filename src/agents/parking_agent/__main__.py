import uvicorn
from config import get_parking_agent_host, get_parking_agent_port
from .app import create_parking_agent_app

if __name__ == "__main__":
    app = create_parking_agent_app()
    uvicorn.run(app, host=get_parking_agent_host(), port=get_parking_agent_port())
