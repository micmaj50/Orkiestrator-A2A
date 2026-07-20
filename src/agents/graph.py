import asyncio

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from agents.state import GraphState, Task, TaskStatus
from agents.orchestrator.Llm import Llm
from agents.orchestrator.Delegator import Delegator
from agents.synthesizer import Synthesizer
from utils.a2a_client import call_sub_agent


ORCHESTRATOR_URL = 'http://127.0.0.1:9999'
GAS_AGENT_URL = 'http://127.0.0.1:9998'
FOOD_AGENT_URL = 'http://127.0.0.1:9997'

ROUTABLE_AGENTS = {'gas_agent', 'food_agent'}


def _build_subagent_catalog() -> AgentCard:
    """Agent card the Delegator shows to the LLM so it knows which sub-agents exist.

    The skill ``id`` of each entry is the routable agent key (``gas_agent`` /
    ``food_agent``) the LLM must put into ``assigned_agent``.
    """

    skills = [
        AgentSkill(
            id='gas_agent',
            name='Gas Station Agent',
            description='Finds nearby gas stations by current location or a named place.',
            input_modes=['text/plain'],
            output_modes=['text/plain'],
            tags=['gas', 'fuel'],
            examples=['find the closest gas stations'],
        ),
        AgentSkill(
            id='food_agent',
            name='Food Agent',
            description='Finds restaurants and dining options, optionally by cuisine and location.',
            input_modes=['text/plain'],
            output_modes=['text/plain'],
            tags=['food', 'restaurants'],
            examples=['find some sushi nearby'],
        ),
    ]

    return AgentCard(
        name='Driver Assistant Orchestrator',
        description='Routes driver requests to the gas_agent or food_agent sub-agents.',
        version='1.0.0',
        default_input_modes=['text/plain'],
        default_output_modes=['text/plain'],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(
                protocol_binding='JSONRPC',
                url=ORCHESTRATOR_URL,
                protocol_version='1.0',
            )
        ],
        skills=skills,
    )


# LLM-backed components are created lazily so that importing / compiling the
# graph does not require an OpenAI API key (only running it does).
_llm: Llm | None = None
_delegator: Delegator | None = None
_synthesizer = Synthesizer()


def _get_llm() -> Llm:
    global _llm
    if _llm is None:
        _llm = Llm()
    return _llm


def _get_delegator() -> Delegator:
    global _delegator
    if _delegator is None:
        _delegator = Delegator(Llm=_get_llm(), AgentCard=_build_subagent_catalog())
    return _delegator


async def orchestrator_node(state: GraphState) -> dict:
    """Orchestrator node: asks the LLM (via Delegator) which sub-agents to call.

    On the first pass it plans the tasks; on loop-backs (``state.tasks`` already
    populated) it leaves the plan untouched so the supervisor loop can drain it.
    """

    if state.tasks:
        return {}

    # Delegator.invoke is synchronous (LangChain chain.invoke); run it off the
    # event loop so it does not block the async sub-agent calls.
    raw = await asyncio.to_thread(_get_delegator().invoke, state, None)

    if isinstance(raw, dict):
        items = raw.get('tasks') or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    tasks: list[Task] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        agent = item.get('assigned_agent')
        # Drop anything the LLM invented that we cannot actually route to.
        if agent not in ROUTABLE_AGENTS:
            continue

        tasks.append(
            Task(
                # Task.id is a str; coerce whatever the LLM returned.
                id=str(item.get('id') or f'{agent}-{idx}'),
                name=str(item.get('name') or agent),
                assigned_agent=agent,
            )
        )

    return {'tasks': tasks}


def route_from_orchestrator(state: GraphState) -> str:
    """Route to the next agent based on the orchestrator's tasks list"""

    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent in ROUTABLE_AGENTS:
            return task.assigned_agent

    return 'response_synthesizer'


async def _run_agent_node(state: GraphState, agent_key: str, agent_url: str) -> dict:
    """Call a sub-agent over A2A, record the result on its task and expose it
    on ``messages`` so the synthesizer can read it."""

    user_text = str(state.user_input.content)

    updated_tasks: list[Task] = []
    produced: list[str] = []
    for task in state.tasks:
        if task.status == TaskStatus.IN_PROGRESS and task.assigned_agent == agent_key:
            try:
                result = await call_sub_agent(user_text, agent_url)
                task.status = TaskStatus.COMPLETED
                task.result = result
            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = f'{agent_key} call failed: {exc}'

            if task.result:
                produced.append(task.result)

        updated_tasks.append(task)

    output: dict = {'tasks': updated_tasks}
    if produced:
        # add_messages reducer appends, so each agent contributes its own turn.
        output['messages'] = [AIMessage(content='\n\n'.join(produced))]
    return output


async def gas_agent_node(state: GraphState) -> dict:
    """Gas sub-agent node: calls the gas station agent over A2A and records the result."""
    return await _run_agent_node(state, 'gas_agent', GAS_AGENT_URL)


async def food_agent_node(state: GraphState) -> dict:
    """Food sub-agent node: calls the food agent over A2A and records the result."""
    return await _run_agent_node(state, 'food_agent', FOOD_AGENT_URL)


async def response_synthesizer_node(state: GraphState) -> dict:
    """Response synthesizer node: asks the LLM (via Synthesizer) to combine the
    sub-agent outputs into a single human-facing answer."""

    has_results = any(task.result for task in state.tasks)
    if not has_results:
        return {
            'messages': [
                AIMessage(
                    content="I couldn't handle that request. Try asking for gas stations or food."
                )
            ]
        }

    # Synthesizer.__call__ is synchronous; run it off the event loop.
    final_text = await asyncio.to_thread(_synthesizer, state, _get_llm(), False)
    if not isinstance(final_text, str):
        final_text = str(final_text)

    return {'messages': [AIMessage(content=final_text)]}


graph_builder = StateGraph(GraphState)

graph_builder.add_node('orchestrator', orchestrator_node)
graph_builder.add_node('gas_agent', gas_agent_node)
graph_builder.add_node('food_agent', food_agent_node)
graph_builder.add_node('response_synthesizer', response_synthesizer_node)

graph_builder.add_edge(START, 'orchestrator')
graph_builder.add_conditional_edges('orchestrator', route_from_orchestrator, {
    'gas_agent': 'gas_agent',
    'food_agent': 'food_agent',
    'response_synthesizer': 'response_synthesizer'
})
graph_builder.add_edge('gas_agent', 'orchestrator')
graph_builder.add_edge('food_agent', 'orchestrator')
graph_builder.add_edge('response_synthesizer', END)

graph = graph_builder.compile()
