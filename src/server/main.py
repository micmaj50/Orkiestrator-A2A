import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from agents.registry import discover_agents
from config import SERVER_HOST, SERVER_PORT, SINGLE_APP_MODE
from server.agent_app import create_agent_app


def create_server_app() -> Starlette:
    """Mount every agent discovered from `agents/*/card.json`."""

    if not SINGLE_APP_MODE:
        raise RuntimeError(
            "The shared Starlette server requires SINGLE_APP_MODE=true. "
            "Use server.run_agent for standalone mode."
        )

    return Starlette(
        routes=[
            Mount(
                definition.mount_path,
                app=create_agent_app(definition.key)
            ) for definition in discover_agents()
        ]
    )


app = create_server_app()

if __name__ == "__main__":
    print(f"Starting Agent Server at http://{SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)