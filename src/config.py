import os

# Default settings for Single App mode
DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8000

# Default settings for Standalone mode
DEFAULT_BIND_HOST = "127.0.0.1"

DEFAULT_ORCHESTRATOR_HOST = "127.0.0.1"
DEFAULT_ORCHESTRATOR_PORT = 9999

DEFAULT_GAS_AGENT_HOST = "127.0.0.1"
DEFAULT_GAS_AGENT_PORT = 9998

DEFAULT_FOOD_AGENT_HOST = "127.0.0.1"
DEFAULT_FOOD_AGENT_PORT = 9997

DEFAULT_PARKING_AGENT_HOST = "127.0.0.1"
DEFAULT_PARKING_AGENT_PORT = 9996

DEFAULT_WEATHER_AGENT_HOST = "127.0.0.1"
DEFAULT_WEATHER_AGENT_PORT = 9995


def is_single_app_mode() -> bool:
    """Check whether the application is running as a single Starlette app."""
    return os.getenv("SINGLE_APP_MODE", "false").lower() == "true"


def get_server_host() -> str:
    return os.getenv("SERVER_HOST", DEFAULT_SERVER_HOST)


def get_server_port() -> int:
    return int(os.getenv("SERVER_PORT", str(DEFAULT_SERVER_PORT)))


def get_bind_host() -> str:
    return os.getenv("A2A_BIND_HOST", DEFAULT_BIND_HOST)



def get_orchestrator_host() -> str:
    return os.getenv("ORCHESTRATOR_HOST", DEFAULT_ORCHESTRATOR_HOST)


def get_orchestrator_port() -> int:
    return int(os.getenv("ORCHESTRATOR_PORT", str(DEFAULT_ORCHESTRATOR_PORT)))


def get_orchestrator_url() -> str:
    if is_single_app_mode():
        return f"http://{get_server_host()}:{get_server_port()}/orchestrator/"
    return f"http://{get_orchestrator_host()}:{get_orchestrator_port()}"



def get_gas_agent_host() -> str:
    return os.getenv("GAS_AGENT_HOST", DEFAULT_GAS_AGENT_HOST)


def get_gas_agent_port() -> int:
    return int(os.getenv("GAS_AGENT_PORT", str(DEFAULT_GAS_AGENT_PORT)))


def get_gas_agent_url() -> str:
    if is_single_app_mode():
        return f"http://{get_server_host()}:{get_server_port()}/gas/"
    return f"http://{get_gas_agent_host()}:{get_gas_agent_port()}"



def get_food_agent_host() -> str:
    return os.getenv("FOOD_AGENT_HOST", DEFAULT_FOOD_AGENT_HOST)


def get_food_agent_port() -> int:
    return int(os.getenv("FOOD_AGENT_PORT", str(DEFAULT_FOOD_AGENT_PORT)))


def get_food_agent_url() -> str:
    if is_single_app_mode():
        return f"http://{get_server_host()}:{get_server_port()}/food/"
    return f"http://{get_food_agent_host()}:{get_food_agent_port()}"



def get_parking_agent_host() -> str:
    return os.getenv("PARKING_AGENT_HOST", DEFAULT_PARKING_AGENT_HOST)


def get_parking_agent_port() -> int:
    return int(os.getenv("PARKING_AGENT_PORT", str(DEFAULT_PARKING_AGENT_PORT)))


def get_parking_agent_url() -> str:
    if is_single_app_mode():
        return f"http://{get_server_host()}:{get_server_port()}/parking/"
    return f"http://{get_parking_agent_host()}:{get_parking_agent_port()}"



def get_weather_agent_host() -> str:
    return os.getenv("WEATHER_AGENT_HOST", DEFAULT_WEATHER_AGENT_HOST)


def get_weather_agent_port() -> int:
    return int(os.getenv("WEATHER_AGENT_PORT", str(DEFAULT_WEATHER_AGENT_PORT)))


def get_weather_agent_url() -> str:
    if is_single_app_mode():
        return f"http://{get_server_host()}:{get_server_port()}/weather/"
    return f"http://{get_weather_agent_host()}:{get_weather_agent_port()}"