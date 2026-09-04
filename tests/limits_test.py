"""Tests for the execution limits."""

import asyncio

import pytest
from a2a.types import TaskState

import config
from utils import a2a_client

# One row per limit: its environment variable, its getter, the default, and a
# different value to prove the environment is read. Adding a limit to
# config.py means adding a row here.
LIMIT_GETTERS = [
    ('LLM_TIMEOUT_SECONDS', config.get_llm_timeout_seconds, 30.0, '45', 45.0),
    ('LLM_MAX_RETRIES', config.get_llm_max_retries, 1, '3', 3),
    ('LLM_MAX_OUTPUT_TOKENS', config.get_llm_max_output_tokens, 1000, '500', 500),
    ('EXTERNAL_API_TIMEOUT_SECONDS', config.get_external_api_timeout_seconds, 15.0, '8', 8.0),
    ('SUB_AGENT_TIMEOUT_SECONDS', config.get_sub_agent_timeout_seconds, 90.0, '15', 15.0),
    ('REQUEST_TIMEOUT_SECONDS', config.get_request_timeout_seconds, 540.0, '20', 20.0),
    ('MAX_TASKS', config.get_max_tasks, 5, '2', 2),
    ('MIN_SKILL_SCORE', config.get_min_skill_score, 0.5, '0.7', 0.7),
]


@pytest.mark.parametrize(('env_var', 'getter', 'default', 'raw', 'expected'), LIMIT_GETTERS)
def test_limit_defaults(monkeypatch, env_var, getter, default, raw, expected):
    """Every limit has a default, so an empty .env still yields a bounded run."""

    monkeypatch.delenv(env_var, raising=False)

    assert getter() == default


@pytest.mark.parametrize(('env_var', 'getter', 'default', 'raw', 'expected'), LIMIT_GETTERS)
def test_limit_reads_the_environment(monkeypatch, env_var, getter, default, raw, expected):
    """Each limit can be tuned per environment without a code change."""

    monkeypatch.setenv(env_var, raw)

    assert getter() == expected


def test_request_timeout_outlasts_every_sub_agent_call(monkeypatch):
    """
    The outer cap must not fire before the per-agent ones. If it does, one slow
    sub-agent takes the whole run down and the answers that did arrive are lost.
    """

    monkeypatch.delenv('REQUEST_TIMEOUT_SECONDS', raising=False)
    monkeypatch.setenv('MAX_TASKS', '5')
    monkeypatch.setenv('SUB_AGENT_TIMEOUT_SECONDS', '90')

    # Tasks run one after another, so their budgets add up.
    assert config.get_request_timeout_seconds() > 5 * 90


def test_recursion_limit_leaves_room_for_a_full_run(monkeypatch):
    """The graph step limit is derived, so it must stay above a valid run."""

    monkeypatch.setenv('MAX_TASKS', '5')

    # Two graph steps per task, plus the delegation and the final synthesis.
    cost_of_a_full_run = 2 * 5 + 2

    assert config.get_graph_recursion_limit() > cost_of_a_full_run


class FakeResolver:
    """Replaces `A2ACardResolver`: the card is irrelevant to these tests."""

    def __init__(self, httpx_client, base_url):
        self.base_url = base_url

    async def get_agent_card(self):
        return object()


class FakeSubAgentClient:
    """Replaces the A2A client: records the context it was called with."""

    def __init__(self):
        self.contexts = []
        self.closed = False

    async def send_message(self, request, *, context=None):
        self.contexts.append(context)

        class Part:
            text = 'answer from the sub-agent'

        class Artifact:
            parts = [Part()]
            metadata = None

        class Status:
            state = TaskState.TASK_STATE_COMPLETED
            message = None

        class Chunk:
            artifacts = [Artifact()]
            status = Status()

        yield Chunk()

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_sub_agent(monkeypatch):
    """Wire the fakes into the A2A helper and hand the client back."""

    client = FakeSubAgentClient()

    async def fake_create_client(agent, client_config):
        return client

    monkeypatch.setattr(a2a_client, 'A2ACardResolver', FakeResolver)
    monkeypatch.setattr(a2a_client, 'create_client', fake_create_client)

    return client


def test_sub_agent_call_carries_the_configured_timeout(monkeypatch, fake_sub_agent):
    """
    Without an explicit context the SDK falls back to a 5s default, which is
    shorter than the LLM call a sub-agent has to make before answering.
    """

    monkeypatch.setenv('SUB_AGENT_TIMEOUT_SECONDS', '42')

    result = asyncio.run(a2a_client.call_sub_agent('find gas', 'http://gas-agent:9998'))

    assert result == (TaskState.TASK_STATE_COMPLETED, 'answer from the sub-agent')
    assert [context.timeout for context in fake_sub_agent.contexts] == [42.0]
    assert fake_sub_agent.closed


from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from langgraph.errors import GraphRecursionError

from agents.orchestrator.agent_executor import OrchestratorExecutor


class FakeMessagePart:
    def __init__(self):
        self.text = "hello"
    def HasField(self, field):
        return True

class FakeMessage:
    def __init__(self, text):
        from a2a.types import Role
        self.text = text
        self.role = Role.ROLE_USER
        self.parts = [FakeMessagePart()]
        self.task_id = "fake-task"
        self.context_id = "fake-context"


from unittest.mock import MagicMock


def create_fake_context(text):
    context = MagicMock(spec=RequestContext)
    context.message = FakeMessage(text)
    context.current_task = None
    return context


class FakeEventQueue(EventQueue):
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


@pytest.mark.parametrize('error', [
    TimeoutError(),
    GraphRecursionError(),
    # The one that used to escape, leaving the task in WORKING and the client waiting.
    RuntimeError('qdrant is unreachable'),
])
def test_a_failing_graph_still_closes_the_task(monkeypatch, error):
    """However the graph gives up, the A2A task has to reach a terminal state."""

    import agents.orchestrator.agent_executor

    executor = OrchestratorExecutor()
    queue = FakeEventQueue()

    monkeypatch.setattr(
        agents.orchestrator.agent_executor,
        'new_task_from_user_message',
        lambda msg: MagicMock(id='1', context_id='2'),
    )

    async def fake_invoke(*args, **kwargs):
        raise error

    monkeypatch.setattr(executor.agent, 'invoke', fake_invoke)

    asyncio.run(executor.execute(create_fake_context('find gas'), queue))

    statuses = [event for event in queue.events if hasattr(event, 'status')]
    assert statuses, 'the task was left without a terminal state'
    assert statuses[-1].status.state == TaskState.TASK_STATE_FAILED


def test_orchestrator_node_drops_tasks_when_limit_exceeded(monkeypatch):
    """If MAX_TASKS is exceeded, orchestrator_node should drop extra tasks and set tasks_dropped=True."""
    from langchain_core.messages import HumanMessage

    import agents.graph
    from agents.graph import orchestrator_node
    from agents.state import GraphState

    monkeypatch.setattr(agents.graph, 'get_max_tasks', lambda: 1)

    class FakeDelegator:
        def invoke(self, state, carData):
            return {"tasks": [{"query": "q1", "assigned_agent": "a1"}, {"query": "q2", "assigned_agent": "a2"}]}

    monkeypatch.setattr(agents.graph, "delegator", FakeDelegator())

    state = GraphState(user_input=HumanMessage(content="test"), messages=[], tasks=[], tasks_dropped=False)

    new_state = asyncio.run(orchestrator_node(state))

    assert new_state["tasks_dropped"] is True
    assert len(new_state["tasks"]) == 1
