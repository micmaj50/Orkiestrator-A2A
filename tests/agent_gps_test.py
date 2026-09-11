"""The car position reaches the sub-agents as message metadata, not as a guess."""

import asyncio
from unittest.mock import MagicMock

import pytest
from a2a.helpers import new_text_message
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types import Role, TaskState

from agents.food_agent.agent_executor import FoodAgentExecutor
from agents.gas_agent.agent_executor import GasStationAgentExecutor
from agents.parking_agent.agent_executor import ParkingAgentExecutor
from agents.weather_agent.agent_executor import WeatherAgentExecutor

EXECUTORS = [
    WeatherAgentExecutor,
    GasStationAgentExecutor,
    FoodAgentExecutor,
    ParkingAgentExecutor,
]


class RecordingAgent:
    """Replaces the real agent: records the position it was asked to search around."""

    def __init__(self):
        self.seen: tuple | None = None

    async def invoke(self, user_request, car_lat=None, car_lng=None):
        self.seen = (car_lat, car_lng)
        return TaskState.TASK_STATE_COMPLETED, 'an answer'


class FakeEventQueue(EventQueue):
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


def run_executor(executor_class, metadata: dict | None) -> tuple:
    message = new_text_message('what is around me', role=Role.ROLE_USER)
    if metadata:
        message.metadata.update(metadata)

    context = MagicMock(spec=RequestContext)
    context.message = message
    context.current_task = None

    agent = RecordingAgent()
    asyncio.run(executor_class(agent=agent).execute(context, FakeEventQueue()))

    return agent.seen


@pytest.mark.parametrize('executor_class', EXECUTORS)
def test_the_agent_searches_around_the_position_the_orchestrator_sent(executor_class):
    assert run_executor(executor_class, {'car_lat': 53.4289, 'car_lng': 14.5530}) == (53.4289, 14.5530)


@pytest.mark.parametrize('executor_class', EXECUTORS)
def test_without_a_position_the_agent_gets_none_instead_of_a_made_up_city(executor_class):
    """No GPS means the agent asks the driver where to look, not that it guesses."""

    assert run_executor(executor_class, None) == (None, None)
