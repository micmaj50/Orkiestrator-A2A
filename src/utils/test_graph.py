"""Simple manual tester for the LangGraph orchestration graph.

Runs the compiled graph end-to-end for a single user query and prints the
sub-agent tasks and the final synthesized answer.

The graph talks to the sub-agents over A2A, so the relevant sub-agent servers
must be running first, e.g.:

    uv run python -m agents.gas_agent     # port 9998
    uv run python -m agents.food_agent    # port 9997

Then, from the repository root:

    uv run python -m utils.test_graph "find gas and food near Big Ben"
"""

import asyncio
import sys

from langchain_core.messages import HumanMessage

from agents.graph import graph
from agents.state import GraphState


async def run_graph(question: str) -> None:
    # Build the initial graph state from the user's question
    state = GraphState(user_input=HumanMessage(content=question))

    # Invoke the graph: orchestrator -> sub-agents (over A2A) -> synthesizer
    result = await graph.ainvoke(state)

    # Show what the orchestrator planned and how each task ended
    print('\n=== TASKS ===')
    tasks = result.get('tasks', [])
    if tasks:
        for task in tasks:
            print(f'- {task.assigned_agent} [{task.status.value}] {task.name}')
    else:
        print('No tasks were planned for this request.')

    # Show the final synthesized answer
    print('\n=== FINAL ANSWER ===')
    messages = result.get('messages', [])
    if messages:
        print(messages[-1].content)
    else:
        print('No final message was produced.')


def get_question_from_cli() -> str:
    if len(sys.argv) > 1:
        return ' '.join(sys.argv[1:])

    return input('user > ').strip()


def main() -> None:
    question = get_question_from_cli()

    if not question:
        print('No question provided')
        return

    asyncio.run(run_graph(question))


if __name__ == '__main__':
    main()
