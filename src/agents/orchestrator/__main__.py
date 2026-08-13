import uvicorn
from config import get_bind_host, get_orchestrator_port
from .app import create_orchestrator_app

if __name__ == "__main__":
    app = create_orchestrator_app()
    uvicorn.run(app, host=get_bind_host(), port=get_orchestrator_port())
