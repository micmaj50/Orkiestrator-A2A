"""Utilities for extracting text from A2A responses"""

from typing import Any

from a2a.types import TaskState


def _carries(a2a_response_chunk: Any, payload: str) -> bool:
    """Tell which payload a response chunk carries.

    A protobuf chunk exposes every field it knows, so an unset one still
    reads as an empty message and cannot be recognised with `getattr`.
    `HasField` answers that; plain objects fall back to an attribute check.
    """

    has_field = getattr(a2a_response_chunk, 'HasField', None)

    if callable(has_field):
        try:
            return bool(has_field(payload))
        except ValueError:
            # The chunk is of another type that has no such field at all.
            return False

    return getattr(a2a_response_chunk, payload, None) is not None


def _parts_text(parts: Any) -> list[str]:
    """Collect the text carried by every textual part."""

    texts: list[str] = []

    for part in parts or []:
        text = getattr(part, 'text', None)
        if isinstance(text, str) and text:
            texts.append(text)

    return texts


def _get_task(a2a_response_chunk: Any) -> Any:
    """Return the wrapped task, or assume the chunk is already a task"""

    if _carries(a2a_response_chunk, 'task'):
        return a2a_response_chunk.task

    return a2a_response_chunk


def extract_artifact_text(a2a_response_chunk: Any) -> str:
    """Extract text from an A2A response chunk.

    An agent answers either with a task that carries artifacts or with a
    plain message, so both shapes are read. Remote agents pick either one,
    and the official samples answer with messages only.

    Also extracts the status message if the task failed.
    """

    if _carries(a2a_response_chunk, 'message'):
        message = a2a_response_chunk.message
        return '\n'.join(_parts_text(getattr(message, 'parts', [])))

    task = _get_task(a2a_response_chunk)

    texts: list[str] = []

    status = getattr(task, 'status', None)
    if status and getattr(status, 'state', None) == TaskState.TASK_STATE_FAILED:
        status_message = getattr(status, 'message', None)
        texts.extend(
            f"SYSTEM ERROR: {text}"
            for text in _parts_text(getattr(status_message, 'parts', []))
        )

    for artifact in getattr(task, 'artifacts', []) or []:
        texts.extend(_parts_text(getattr(artifact, 'parts', [])))

    return '\n'.join(texts)
