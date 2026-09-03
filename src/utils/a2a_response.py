"""Utilities for extracting text from A2A responses"""

from typing import Any

from a2a.types import TaskState


def _get_task(a2a_response_chunk: Any) -> Any:
    """Return the wrapped task, or assume the chunk is already a task"""
    return getattr(a2a_response_chunk, "task", a2a_response_chunk)

def extract_artifact_text(a2a_response_chunk: Any) -> str:
    """Extract text from artifact parts in an A2A response chunk.

    Also extracts the status message if the task failed.
    """
    task = _get_task(a2a_response_chunk)
    artifacts = getattr(task, 'artifacts', [])

    texts: list[str] = []

    status = getattr(task, 'status', None)
    if status and getattr(status, 'state', None) == TaskState.TASK_STATE_FAILED:
        parts = getattr(getattr(status, 'message', None), 'parts', [])
        for part in parts:
            text = getattr(part, 'text', None)
            if isinstance(text, str):
                texts.append(f"SYSTEM ERROR: {text}")

    for artifact in artifacts:
        parts = getattr(artifact, 'parts', [])
        for part in parts:
            text = getattr(part, 'text', None)
            if isinstance(text, str):
                texts.append(text)

    return '\n'.join(texts)
