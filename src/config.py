import os


DEFAULT_BIND_HOST = "127.0.0.1"

DEFAULT_ORCHESTRATOR_HOST = "127.0.0.1"
DEFAULT_ORCHESTRATOR_PORT = 9999

DEFAULT_GAS_AGENT_HOST = "127.0.0.1"
DEFAULT_GAS_AGENT_PORT = 9998

DEFAULT_FOOD_AGENT_HOST = "127.0.0.1"
DEFAULT_FOOD_AGENT_PORT = 9997


def get_bind_host() -> str:
    return os.getenv("A2A_BIND_HOST", DEFAULT_BIND_HOST)


def get_orchestrator_host() -> str:
    return os.getenv("ORCHESTRATOR_HOST", DEFAULT_ORCHESTRATOR_HOST)


def get_orchestrator_port() -> int:
    return int(os.getenv("ORCHESTRATOR_PORT", str(DEFAULT_ORCHESTRATOR_PORT)))


def get_orchestrator_url() -> str:
    return (
            f"http://{get_orchestrator_host()}:"
            f"{get_orchestrator_port()}"
    )



def get_gas_agent_host() -> str:
    return os.getenv("GAS_AGENT_HOST", DEFAULT_GAS_AGENT_HOST)


def get_gas_agent_port() -> int:
    return int(os.getenv("GAS_AGENT_PORT", str(DEFAULT_GAS_AGENT_PORT)))


def get_gas_agent_url() -> str:
    return (
            f"http://{get_gas_agent_host()}:"
            f"{get_gas_agent_port()}"
    )



def get_food_agent_host() -> str:
    return os.getenv("FOOD_AGENT_HOST", DEFAULT_FOOD_AGENT_HOST)


def get_food_agent_port() -> int:
    return int(os.getenv("FOOD_AGENT_PORT", str(DEFAULT_FOOD_AGENT_PORT)))


def get_food_agent_url() -> str:
    return (
            f"http://{get_food_agent_host()}:"
            f"{get_food_agent_port()}"
    )
