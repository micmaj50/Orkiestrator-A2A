import uvicorn
from config import get_gas_agent_host, get_gas_agent_port
from .app import create_gas_agent_app

if __name__ == "__main__":
    app = create_gas_agent_app()
    uvicorn.run(app, host=get_gas_agent_host(), port=get_gas_agent_port())
