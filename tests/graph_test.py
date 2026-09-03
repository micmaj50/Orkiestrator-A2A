"""End-to-end tests for the orchestrator -> sub-agents -> synthesizer graph.
"""

import asyncio

import pytest
from langchain_core.messages import HumanMessage

from agents import graph as graph_module
from agents.graph import graph, route_from_orchestrator
from agents.state import GraphState, Task, TaskStatus
from config import (
    get_food_agent_url,
    get_gas_agent_url,
    get_parking_agent_url,
    get_weather_agent_url,
)

FINAL_ANSWER = 'Final answer for the driver.'
FALLBACK = "I couldn't handle that request."


class FakeLlm:
    """Replaces `Llm`: the delegation as JSON, the summary as plain text."""

    def __init__(self, tasks: list[dict]):
        self.tasks = tasks
        self.synthesizer_inputs: dict | None = None

    def __call__(self, prompt, inputs: dict, asJSON: bool):
        # Rendering the real template catches a missing or renamed variable.
        prompt.invoke(inputs)

        if asJSON:
            return {'tasks': self.tasks}

        self.synthesizer_inputs = inputs
        return FINAL_ANSWER


class FakeSubAgents:
    """Replaces `call_sub_agent`: records the query and the target URL."""

    def __init__(self, broken_url: str | None = None):
        self.calls: list[tuple[str, str]] = []
        self.broken_url = broken_url

    async def __call__(self, user_request: str, agent_url: str) -> str:
        self.calls.append((user_request, agent_url))

        if agent_url == self.broken_url:
            raise RuntimeError('sub-agent is down')

        return f'answer from {agent_url}'


def task(agent: str, query: str | None = None, task_id=1) -> dict:
    """One task as the delegator prompt asks the LLM to return it."""

    return {'id': task_id, 'query': query, 'assigned_agent': agent}


@pytest.fixture
def run_flow(monkeypatch):
    """Wire the fakes into the graph module and run the graph."""

    def _run(user_request: str, tasks: list[dict], broken_url: str | None = None):
        llm = FakeLlm(tasks)
        sub_agents = FakeSubAgents(broken_url)

        monkeypatch.setattr(graph_module, 'llm', llm)
        # A module-level singleton, so it is rebuilt with the fake LLM.
        monkeypatch.setattr(graph_module, 'delegator', None)
        monkeypatch.setattr(graph_module, 'call_sub_agent', sub_agents)

        state = GraphState(user_input=HumanMessage(content=user_request))
        return asyncio.run(graph.ainvoke(state)), llm, sub_agents

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
        ('gas station in Radom', get_gas_agent_url()),
        ('weather in Radom', get_weather_agent_url()),
    ]
    assert all(task.status == TaskStatus.COMPLETED for task in result['tasks'])

    # Both answers landed on messages and the synthesizer had the last word.
    assert [message.content for message in result['messages']] == [
        f'answer from {get_gas_agent_url()}',
        f'answer from {get_weather_agent_url()}',
        FINAL_ANSWER,
    ]

    # The synthesizer saw the original request and both agent answers.
    assert llm.synthesizer_inputs['user_request'] == 'Gas and weather in Radom?'
    assert get_gas_agent_url() in llm.synthesizer_inputs['agent_answers']
    assert get_weather_agent_url() in llm.synthesizer_inputs['agent_answers']


@pytest.mark.parametrize(
    ('agent', 'expected_url'),
    [
        ('gas_agent', get_gas_agent_url()),
        ('food_agent', get_food_agent_url()),
        ('parking_agent', get_parking_agent_url()),
        ('weather_agent', get_weather_agent_url()),
    ],
)
def test_every_agent_is_reachable_from_the_orchestrator(run_flow, agent, expected_url):
    """The shared agent node reaches every registered agent, whatever the key."""

    result, _, sub_agents = run_flow('do the thing', [task(agent, 'a query')])

    assert sub_agents.calls == [('a query', expected_url)]
    assert result['messages'][-1].content == FINAL_ANSWER


def test_agent_node_falls_back_to_the_user_input_when_query_is_missing(run_flow):
    """A task without a query still reaches the agent, using the raw user input."""

    _, _, sub_agents = run_flow('I am hungry', [task('food_agent')])

    assert sub_agents.calls == [('I am hungry', get_food_agent_url())]


def test_failing_sub_agent_is_recorded_and_does_not_break_the_flow(run_flow):
    """A dead sub-agent marks its task FAILED, the rest of the flow continues."""

    result, llm, _ = run_flow(
        'Gas and food?',
        [task('gas_agent', 'find gas', task_id=1), task('food_agent', 'find food', task_id=2)],
        broken_url=get_gas_agent_url(),
    )

    gas_task, food_task = result['tasks']
    assert gas_task.status == TaskStatus.FAILED
    assert gas_task.result == 'Gas Station Agent call failed: sub-agent is down'
    assert food_task.status == TaskStatus.COMPLETED

    # The failure is handed to the synthesizer instead of being swallowed.
    assert 'Gas Station Agent call failed' in llm.synthesizer_inputs['agent_answers']


@pytest.mark.parametrize(
    'tasks',
    [
        pytest.param([], id='no_tasks'),
        pytest.param([task('rocket_agent', 'launch a rocket')], id='unknown_agent'),
    ],
)
def test_flow_without_routable_tasks_returns_the_fallback(run_flow, tasks):
    """Nothing to route means no synthesis call, just the canned message."""

    result, llm, sub_agents = run_flow('Fly me to the moon', tasks)

    assert result['tasks'] == []
    assert sub_agents.calls == []
    assert llm.synthesizer_inputs is None
    assert result['messages'][-1].content.startswith(FALLBACK)


@pytest.mark.parametrize(
    ('tasks', 'expected'),
    [
        ([], 'response_synthesizer'),
        ([Task(id=1, assigned_agent='gas_agent')], 'agent_node'),
        (
            [
                Task(id=1, assigned_agent='gas_agent', status=TaskStatus.COMPLETED),
                Task(id=2, assigned_agent='food_agent'),
            ],
            'agent_node',
        ),
    ],
)
def test_route_from_orchestrator(tasks, expected):
    """Any pending task goes to the shared agent node, then to the synthesizer."""

    state = GraphState(user_input=HumanMessage(content='anything'), tasks=tasks)

    assert route_from_orchestrator(state) == expected
