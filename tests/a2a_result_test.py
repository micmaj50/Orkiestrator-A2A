"""Tests for the state a sub-agent ends on and how far it survives.

A sub-agent answering is not a sub-agent succeeding. These pin the two places
that used to lose the difference: the A2A wire a sub-agent writes to, and the
client reading it.
"""

import asyncio
from types import SimpleNamespace

import pytest
from a2a.helpers import new_text_message
from a2a.types import Role, TaskState

from agents.parking_agent.agent_executor import ParkingAgentExecutor
from utils import a2a_client
from utils.a2a_response import extract_agent_result


def fake_task(state, artifact=None, status=None):
    """The shape the extractor reads: a state, maybe an artifact, maybe a message."""

    parts = lambda text: SimpleNamespace(parts=[SimpleNamespace(text=text)])

    return SimpleNamespace(
        status=SimpleNamespace(state=state, message=parts(status) if status else None),
        artifacts=[parts(artifact)] if artifact else [],
    )


@pytest.mark.parametrize('state', [TaskState.TASK_STATE_SUBMITTED, TaskState.TASK_STATE_WORKING])
def test_a_running_task_carries_no_outcome_yet(state):
    """Reading a progress message as an answer is how a stalled call looked like a success."""

    assert extract_agent_result(fake_task(state, status='Processing...')) is None


@pytest.mark.parametrize('state', [
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_INPUT_REQUIRED,
    # Not obviously terminal, and each used to come back as an empty success.
    TaskState.TASK_STATE_REJECTED,
    TaskState.TASK_STATE_CANCELED,
    TaskState.TASK_STATE_AUTH_REQUIRED,
])
def test_every_terminal_state_comes_back_with_its_answer(state):
    assert extract_agent_result(fake_task(state, artifact='the answer')) == (state, 'the answer')


def test_a_failed_task_explains_itself_from_the_status_message():
    """A failure usually publishes no artifact, so the reason comes off the status."""

    task = fake_task(TaskState.TASK_STATE_FAILED, status='WEATHER_API_KEY is missing')

    assert extract_agent_result(task) == (TaskState.TASK_STATE_FAILED, 'WEATHER_API_KEY is missing')


def call_with(monkeypatch, chunks):
    """Run `call_sub_agent` against a sub-agent answering with these chunks."""

    class FakeClient:
        async def send_message(self, request, *, context=None):
            for chunk in chunks:
                yield chunk

        async def close(self):
            pass

    class FakeResolver:
        def __init__(self, **kwargs):
            pass

        async def get_agent_card(self):
            return object()

    async def create_client(**kwargs):
        return FakeClient()

    monkeypatch.setattr(a2a_client, 'A2ACardResolver', FakeResolver)
    monkeypatch.setattr(a2a_client, 'create_client', create_client)

    return asyncio.run(a2a_client.call_sub_agent('find gas', 'http://gas-agent:9998'))


@pytest.mark.parametrize(('chunks', 'reason'), [
    ([fake_task(TaskState.TASK_STATE_COMPLETED)], 'a success with no answer in it'),
    ([fake_task(TaskState.TASK_STATE_WORKING, status='working')], 'never reaching a terminal state'),
])
def test_a_non_answer_is_a_failure(monkeypatch, chunks, reason):
    """Both used to come back as an empty success and leave the synthesizer inventing one."""

    state, _ = call_with(monkeypatch, chunks)

    assert state == TaskState.TASK_STATE_FAILED, reason


def test_the_last_terminal_chunk_wins(monkeypatch):
    """State and text come off the same chunk, so they cannot drift apart."""

    result = call_with(monkeypatch, [
        fake_task(TaskState.TASK_STATE_WORKING, status='working'),
        fake_task(TaskState.TASK_STATE_FAILED, status='the API is down'),
    ])

    assert result == (TaskState.TASK_STATE_FAILED, 'the API is down')


@pytest.mark.parametrize('state', [
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_INPUT_REQUIRED,
    TaskState.TASK_STATE_FAILED,
])
def test_a_sub_agent_reports_how_it_ended_on_the_wire(state):
    """Every sub-agent used to close its task as COMPLETED whatever happened inside it."""

    class StubAgent:
        async def invoke(self, user_request, car_lat=None, car_lng=None):
            return state, 'what it had to say'

    class FakeQueue:
        def __init__(self):
            self.events = []

        async def enqueue_event(self, event):
            self.events.append(event)

    context = SimpleNamespace(
        message=new_text_message('find parking', role=Role.ROLE_USER),
        current_task=None,
    )
    queue = FakeQueue()

    asyncio.run(ParkingAgentExecutor(agent=StubAgent()).execute(context, queue))

    statuses = [event for event in queue.events if hasattr(event, 'status')]
    assert statuses[-1].status.state == state
