import argparse
import uvicorn

from config import A2A_BIND_HOST, SINGLE_APP_MODE, get_agent_port
from server.agent_app import create_agent_app

def run_agent(agent_key: str) -> None:
    if SINGLE_APP_MODE:
        raise RuntimeError(
            "The standalone runner requires SINGLE_APP_MODE=false. "
            "Use server.main for the shared application."
        )

    uvicorn.run(
        create_agent_app(agent_key),
        host=A2A_BIND_HOST,
        port=get_agent_port(agent_key)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent")
    args = parser.parse_args()

    run_agent(args.agent)


if __name__ == "__main__":
    main()