"""Utilities for extracting text from A2A responses"""

from typing import Any

def _get_task(a2a_response_chunk: Any) -> Any:
    """Return the wrapped task, or assume the chunk is already a task"""
    return getattr(a2a_response_chunk, "task", a2a_response_chunk)

def extract_artifact_text(a2a_response_chunk: Any) -> str:
    """Extract text from artifact parts in an A2A response chunk.
    
    Only task.artifacts[*].parts[*].text is read. Status and history
    are ignored because they do not represent the final answer.
    https://a2a-protocol.org/latest/definitions/
    """
    task = _get_task(a2a_response_chunk)
    artifacts = getattr(task, 'artifacts', [])

    texts: list[str] = []

    for artifact in artifacts: 
        parts = getattr(artifact, 'parts', None)

        for part in parts:
            text = getattr(part, 'text', None)

            if isinstance(text, str):
                texts.append(text)

    return '\n'.join(texts)
