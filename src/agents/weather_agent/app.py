from config import MOCK_MODE
from .agent_executor import (
    WeatherAgentExecutor,
    WeatherAgent,
    MockWeatherAgent
)


def create_executor() -> WeatherAgentExecutor:
    """Create the Weather Agent implementation used by shared app factory."""

    active_agent = MockWeatherAgent() if MOCK_MODE else WeatherAgent()
    return WeatherAgentExecutor(agent=active_agent)