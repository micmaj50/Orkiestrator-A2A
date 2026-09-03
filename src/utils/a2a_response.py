"""Utilities for extracting text from A2A responses"""

from typing import Any

from a2a.types import TaskState


# The states that mean a sub-agent is done. Anything else - submitted, working -
# is progress, and reading text out of it would report a progress message as an
# answer.
TERMINAL_STATES = frozenset({
    TaskState.TASK_STATE_COMPLETED,
    TaskState.TASK_STATE_INPUT_REQUIRED,
    TaskState.TASK_STATE_FAILED,
    TaskState.TASK_STATE_REJECTED,
    TaskState.TASK_STATE_CANCELED,
    TaskState.TASK_STATE_AUTH_REQUIRED,
})


def _get_task(a2a_response_chunk: Any) -> Any:
    """Return the wrapped task, or assume the chunk is already a task"""
    return getattr(a2a_response_chunk, "task", a2a_response_chunk)


def _part_texts(container: Any) -> list[str]:
    """Every text part of an artifact or a message."""
    return [
        part.text for part in getattr(container, 'parts', None) or []
        if isinstance(getattr(part, 'text', None), str) and part.text
    ]


def extract_artifact_text(a2a_response_chunk: Any) -> str:
    """Extract text from artifact parts in an A2A response chunk.

    Artifacts hold the answer. A task that produced none - a failed one,
    usually - explains itself in the status message instead.
    https://a2a-protocol.org/latest/definitions/
    """
    task = _get_task(a2a_response_chunk)

    texts: list[str] = []

    for artifact in getattr(task, 'artifacts', []):
        texts.extend(_part_texts(artifact))

    status = getattr(task, 'status', None)

    return '\n'.join(texts) or '\n'.join(_part_texts(getattr(status, 'message', None)))


def extract_agent_result(a2a_response_chunk: Any) -> tuple[TaskState, str] | None:
    """Read one A2A response chunk as a finished sub-agent result.

    Returns the state the sub-agent ended on and what it had to say, or None
    while the task is still running.
    """
    task = _get_task(a2a_response_chunk)
    state = getattr(getattr(task, 'status', None), 'state', None)

    if state not in TERMINAL_STATES:
        return None

    return state, extract_artifact_text(task)
