"""Tests for the state a sub-agent ends on and how far it survives.

A sub-agent answering is not a sub-agent succeeding. These pin the two places
that used to lose the difference: the A2A wire a sub-agent writes to, and the
client reading it.
"""

import asyncio

import pytest
from a2a.types import TaskState

from utils import a2a_client
from utils.a2a_response import extract_agent_result


class FakeArtifact:
    def __init__(self, text):
        self.parts = [type('Part', (), {'text': text})()]


class FakeTask:
    """The shape the extractor reads: a state, artifacts, a status message."""

    def __init__(self, state, artifacts=(), status_text=None):
        message = None

        if status_text is not None:
            message = type('Message', (), {'parts': [type('Part', (), {'text': status_text})()]})()

        self.status = type('Status', (), {'state': state, 'message': message})()
        self.artifacts = list(artifacts)


@pytest.mark.parametrize('state', [TaskState.TASK_STATE_SUBMITTED, TaskState.TASK_STATE_WORKING])
def test_a_running_task_carries_no_outcome_yet(state):
    """Reading a progress message as an answer is how a stalled call looked like a success."""

    assert extract_agent_result(FakeTask(state, status_text='Processing...')) is None


@pytest.mark.parametrize('state', [
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_REJECTED,
    TaskState.TASK_STATE_CANCELED,
    TaskState.TASK_STATE_AUTH_REQUIRED,
    TaskState.TASK_STATE_INPUT_REQUIRED,
])
def test_every_terminal_state_comes_back_with_its_answer(state):
    """A failed sub-agent used to reach the orchestrator looking like a completed one."""

    result = extract_agent_result(FakeTask(state, [FakeArtifact('the answer')]))

    assert result == (state, 'the answer')


def test_a_failed_task_explains_itself_from_the_status_message():
    """A failure usually publishes no artifact, so the reason comes off the status."""

    task = FakeTask(TaskState.TASK_STATE_FAILED, status_text='WEATHER_API_KEY is missing')

    assert extract_agent_result(task) == (TaskState.TASK_STATE_FAILED, 'WEATHER_API_KEY is missing')


def call_with_chunks(monkeypatch, chunks) -> tuple[TaskState, str]:
    """Run `call_sub_agent` against a sub-agent answering with these chunks."""

    class FakeClient:
        async def send_message(self, request, *, context=None):
            for chunk in chunks:
                yield chunk

        async def close(self):
            pass

    class FakeResolver:
        def __init__(self, httpx_client, base_url):
            pass

        async def get_agent_card(self):
            return object()

    async def fake_create_client(agent, client_config):
        return FakeClient()

    monkeypatch.setattr(a2a_client, 'A2ACardResolver', FakeResolver)
    monkeypatch.setattr(a2a_client, 'create_client', fake_create_client)

    return asyncio.run(a2a_client.call_sub_agent('find gas', 'http://gas-agent:9998'))


def test_a_completed_task_with_no_answer_is_a_failure(monkeypatch):
    """This is what let the synthesizer turn an empty string into an invented answer."""

    result = call_with_chunks(monkeypatch, [FakeTask(TaskState.TASK_STATE_COMPLETED)])

    assert result[0] == TaskState.TASK_STATE_FAILED


def test_a_sub_agent_that_never_finishes_is_a_failure(monkeypatch):
    """Chunks that never reach a terminal state used to come back as an empty success."""

    result = call_with_chunks(monkeypatch, [FakeTask(TaskState.TASK_STATE_WORKING, status_text='working')])

    assert result[0] == TaskState.TASK_STATE_FAILED


def test_the_last_terminal_chunk_wins(monkeypatch):
    """Outcome and text come off the same chunk, so they cannot drift apart."""

    result = call_with_chunks(monkeypatch, [
        FakeTask(TaskState.TASK_STATE_WORKING, status_text='working'),
        FakeTask(TaskState.TASK_STATE_FAILED, status_text='the API is down'),
    ])

    assert result == (TaskState.TASK_STATE_FAILED, 'the API is down')


class FakeEventQueue:
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


class StubAgent:
    def __init__(self, result):
        self.result = result

    async def invoke(self, user_request, car_lat=None, car_lng=None):
        return self.result


class FakeContext:
    def __init__(self, text):
        from a2a.helpers import new_text_message
        from a2a.types import Role

        self.message = new_text_message(text, role=Role.ROLE_USER)
        self.current_task = None


@pytest.mark.parametrize('expected', [
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_INPUT_REQUIRED,
    TaskState.TASK_STATE_FAILED,
])
def test_a_sub_agent_reports_how_it_ended_on_the_wire(expected):
    """Every sub-agent used to close its task as COMPLETED whatever had happened inside it."""

    from agents.parking_agent.agent_executor import ParkingAgentExecutor

    queue = FakeEventQueue()
    agent = StubAgent((expected, 'what the agent had to say'))
    asyncio.run(ParkingAgentExecutor(agent=agent).execute(FakeContext('find parking'), queue))

    statuses = [event for event in queue.events if hasattr(event, 'status')]

    assert statuses[-1].status.state == expected
