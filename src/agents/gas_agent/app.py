from config import MOCK_MODE
from .agent_executor import (
    GasStationAgentExecutor,
    GasStationAgent,
    MockGasStationAgent
)


def create_executor() -> GasStationAgentExecutor:
    """Create the Gas Agent implementation used by shared app factory."""

    active_agent = MockGasStationAgent() if MOCK_MODE else GasStationAgent()
    return GasStationAgentExecutor(agent=active_agent)