from config import MOCK_MODE
from .agent_executor import (
    ParkingAgentExecutor,
    ParkingAgent,
    MockParkingAgent
)


def create_executor() -> ParkingAgentExecutor:
    """Create the Parking Agent implementation used by shared app factory."""

    active_agent = MockParkingAgent() if MOCK_MODE else ParkingAgent()
    return ParkingAgentExecutor(agent=active_agent)