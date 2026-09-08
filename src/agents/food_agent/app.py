from config import MOCK_MODE
from .agent_executor import (
    FoodAgentExecutor,
    FoodAgent,
    MockFoodAgent
)


def create_executor() -> FoodAgentExecutor:
    """Create the Food Agent implementation used by shared app factory."""

    active_agent = MockFoodAgent() if MOCK_MODE else FoodAgent()
    return FoodAgentExecutor(agent=active_agent)