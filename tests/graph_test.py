"""End-to-end tests for the orchestrator -> sub-agents -> synthesizer graph.
"""

import asyncio
import uuid

import pytest
from langchain_core.messages import HumanMessage

from agents import graph as graph_module
from agents.graph import graph, route_from_orchestrator
from agents.state import GraphState, WorkItem, WorkItemStatus
from config import get_agent_url
from a2a.types import TaskState

FINAL_ANSWER = 'Final answer for the driver.'
FALLBACK = "I couldn't handle that request."

GAS_AGENT_URL = get_agent_url("gas_agent")
FOOD_AGENT_URL = get_agent_url("food_agent")
PARKING_AGENT_URL = get_agent_url("parking_agent")
WEATHER_AGENT_URL = get_agent_url("weather_agent")

class FakeLlm:
    """Replaces `Llm`: the delegation as JSON, the summary as plain text."""

    def __init__(self, tasks: list[dict]):
        self.tasks = tasks
        self.synthesizer_inputs: dict | None = None

    def __call__(self, prompt, inputs: dict, asJSON: bool, observation_name: str = ""):
        # Rendering the real template catches a missing or renamed variable.
        prompt.invoke(inputs)

        if observation_name == "task_division_verification":
            return {
                "valid": True,
                "issues": [],
                "feedback": ""
            }

        if observation_name == "task_division_selection":
            return {
                "selected_candidate": 2,
                "reason": "Candidate 2 is better."
            }

        if asJSON:
            return {'tasks': self.tasks}

        self.synthesizer_inputs = inputs
        return FINAL_ANSWER


class FakeSubAgents:
    """Replaces `call_sub_agent`: records the query and the target URL."""

    def __init__(self, broken_url: str | None = None):
        self.calls: list[tuple[str, str]] = []
        self.broken_url = broken_url

    async def __call__(self, user_request: str, agent_url: str) -> tuple:
        self.calls.append((user_request, agent_url))

        if agent_url == self.broken_url:
            raise RuntimeError('sub-agent is down')

        return TaskState.TASK_STATE_COMPLETED, f'answer from {agent_url}'


def task(agent: str, query: str | None = None, task_id=1) -> dict:
    """One task as the delegator prompt asks the LLM to return it."""

    return {'id': task_id, 'query': query, 'assigned_agent': agent}


@pytest.fixture
def run_flow(monkeypatch):
    """Wire the fakes into the graph module and run the graph."""

    def _run(user_request: str, tasks: list[dict], broken_url: str | None = None, thread_id: str | None = None):
        llm = FakeLlm(tasks)
        sub_agents = FakeSubAgents(broken_url)

        # Build query→agent mapping so search_skill returns the delegator's
        # assignment without loading the real embedding model.
        query_to_agent = {}
        for t in tasks:
            q = t.get('query', '')
            query_to_agent[str(q)] = t.get('assigned_agent')

        def fake_search_skill(_client, query_text):
            return query_to_agent.get(str(query_text))

        monkeypatch.setattr(graph_module, 'llm', llm)
        # A module-level singleton, so it is rebuilt with the fake LLM.
        monkeypatch.setattr(graph_module, 'delegator', None)
        monkeypatch.setattr(graph_module, 'call_sub_agent', sub_agents)
        monkeypatch.setattr(graph_module, 'search_skill', fake_search_skill)
        # Prevent get_qdrant_client from loading the real embedding model.
        monkeypatch.setattr(graph_module, 'qdrant_client', object())

        state = GraphState(
            user_input=HumanMessage(content=user_request),
            messages=[HumanMessage(content=user_request)],
            tasks=[],
            )
        t_id = thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": t_id}}
        return asyncio.run(graph.ainvoke(state, config)), llm, sub_agents

    return _run


def test_flow_fans_out_to_two_agents_and_synthesizes(run_flow):
    """Orchestrator -> agent_node (gas) -> orchestrator -> agent_node (weather) -> synthesizer."""

    result, llm, sub_agents = run_flow(
        'Gas and weather in Radom?',
        [
            task('gas_agent', 'gas station in Radom', task_id=1),
            task('weather_agent', 'weather in Radom', task_id=2),
        ],
    )

    # Every task reached its own agent, with its own query.
    assert sub_agents.calls == [
        ('gas station in Radom', GAS_AGENT_URL),
        ('weather in Radom', WEATHER_AGENT_URL),
    ]
    assert all(task.status == WorkItemStatus.COMPLETED for task in result['tasks'])

    # The synthesizer had the last word
    assert result['messages'][-1].content == FINAL_ANSWER

    # The synthesizer saw the original request and both agent answers.
    assert llm.synthesizer_inputs['user_request'] == 'Gas and weather in Radom?'
    assert GAS_AGENT_URL in llm.synthesizer_inputs['agent_answers']
    assert WEATHER_AGENT_URL in llm.synthesizer_inputs['agent_answers']


def test_conversation_memory_is_isolated_by_thread_id(run_flow):
    """Memory is kept for the same thread_id and isolated from others."""

    # First request in thread_1
    result1, _, _ = run_flow(
        'What about Warsaw?',
        [],
        thread_id='thread_1'
    )
    # 2 messages: user input + fallback response
    assert len(result1['messages']) == 2

    # Second request in thread_1
    result2, _, _ = run_flow(
        'And there?',
        [],
        thread_id='thread_1'
    )
    # 4 messages: 2 from before + 2 new
    assert len(result2['messages']) == 4

    # Request in thread_2
    result3, _, _ = run_flow(
        'What about Radom?',
        [],
        thread_id='thread_2'
    )
    # New thread, isolated memory, only 2 messages
    assert len(result3['messages']) == 2


@pytest.mark.parametrize(
    ('agent', 'expected_url'),
    [
        ('gas_agent', GAS_AGENT_URL),
        ('food_agent', FOOD_AGENT_URL),
        ('parking_agent', PARKING_AGENT_URL),
        ('weather_agent', WEATHER_AGENT_URL),
    ],
)
def test_every_agent_is_reachable_from_the_orchestrator(run_flow, agent, expected_url):
    """The shared agent node reaches every registered agent, whatever the key."""

    result, _, sub_agents = run_flow('do the thing', [task(agent, 'a query')])

    assert sub_agents.calls == [('a query', expected_url)]
    assert result['messages'][-1].content == FINAL_ANSWER


def test_agent_node_falls_back_to_the_user_input_when_query_is_missing(monkeypatch):
    """A task without a query still reaches the agent, using the raw user input."""

    sub_agents = FakeSubAgents()

    monkeypatch.setattr(
        graph_module,
        "call_sub_agent",
        sub_agents
    )

    state = GraphState(
        user_input=HumanMessage(content="I am hungry"),
        tasks=[
            WorkItem(
                id=1,
                assigned_agent="food_agent",
                query=None
            )
        ]
    )

    result = asyncio.run(graph_module.agent_node(state))

    assert sub_agents.calls == [("I am hungry", FOOD_AGENT_URL)]

    assert result["tasks"][0].status == WorkItemStatus.COMPLETED

def test_failing_sub_agent_is_recorded_and_does_not_break_the_flow(run_flow):
    """A dead sub-agent marks its task FAILED, the rest of the flow continues."""

    result, llm, _ = run_flow(
        'Gas and food?',
        [task('gas_agent', 'find gas', task_id=1), task('food_agent', 'find food', task_id=2)],
        broken_url=GAS_AGENT_URL,
    )

    gas_task, food_task = result['tasks']
    assert gas_task.status == WorkItemStatus.FAILED
    assert gas_task.result == 'Gas Station Agent call failed: sub-agent is down'
    assert food_task.status == WorkItemStatus.COMPLETED

    # The failure is handed to the synthesizer instead of being swallowed.
    assert 'Gas Station Agent call failed' in llm.synthesizer_inputs['agent_answers']


def test_flow_without_tasks_returns_the_fallback(run_flow):
    """Nothing to route means no synthesis call, just the canned message."""

    result, llm, sub_agents = run_flow('Fly me to the moon', [])

    assert result["tasks"] == []
    assert sub_agents.calls == []
    assert llm.synthesizer_inputs is None
    assert result['messages'][-1].content.startswith(FALLBACK)


def test_flow_with_unknown_agent_records_failure(run_flow):
    result, llm, sub_agents = run_flow("Fly me to the moon", [task("rocket_agent", "launch a rocket")])

    failed_task = result["tasks"][0]

    assert failed_task.status == WorkItemStatus.FAILED
    assert failed_task.result == "No agent matched this part of the request."
    assert sub_agents.calls == []

    assert llm.synthesizer_inputs is not None
    assert "No agent matched this part of the request." in (llm.synthesizer_inputs["agent_answers"])
    assert result["messages"][-1].content == FINAL_ANSWER


@pytest.mark.parametrize(
    ('tasks', 'expected'),
    [
        ([], 'response_synthesizer'),
        ([WorkItem(id=1, assigned_agent='gas_agent')], 'agent_node'),
        (
            [
                WorkItem(id=1, assigned_agent='gas_agent', status=WorkItemStatus.COMPLETED),
                WorkItem(id=2, assigned_agent='food_agent'),
            ],
            'agent_node',
        ),
    ],
)
def test_route_from_orchestrator(tasks, expected):
    """Any pending task goes to the shared agent node, then to the synthesizer."""

    state = GraphState(
        user_input=HumanMessage(content='anything'),
        messages=[HumanMessage(content='anything')],
        tasks=tasks,
    )

    assert route_from_orchestrator(state) == expected


@pytest.mark.parametrize(('task_state', 'expected'), [
    (TaskState.TASK_STATE_COMPLETED, WorkItemStatus.COMPLETED),
    (TaskState.TASK_STATE_INPUT_REQUIRED, WorkItemStatus.NEED_CONTEXT),
    (TaskState.TASK_STATE_FAILED, WorkItemStatus.FAILED),
    (TaskState.TASK_STATE_REJECTED, WorkItemStatus.FAILED),
])
def test_how_the_sub_agent_ended_becomes_the_work_item_status(monkeypatch, task_state, expected):
    """A sub-agent that answered is not a sub-agent that succeeded."""

    async def sub_agent(user_request, agent_url):
        return task_state, 'what the agent said'

    monkeypatch.setattr(graph_module, 'call_sub_agent', sub_agent)

    state = GraphState(
        user_input=HumanMessage(content='find gas'),
        tasks=[WorkItem(id=1, assigned_agent='gas_agent', query='find gas')],
    )

    result = asyncio.run(graph_module.agent_node(state))

    assert result['tasks'][0].status == expected
