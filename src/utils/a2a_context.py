"""Read the vehicle-context subset the orchestrator attached to an A2A request.

The orchestrator sends a per-agent (class:AgentContext) as a data Part on the
request message.
Sub-agents use this to recover the car's location instead of relying on a hard-coded default.
"""

from typing import Any

from a2a.helpers import get_data_parts

from contracts.agent_request import AgentContext


def extract_coordinates(
    message: Any,
    default_lat: float,
    default_lng: float,
) -> tuple[float, float]:
    """Return ``(latitude, longitude)`` from the request context, or the defaults.

    Missing, empty or malformed data Parts fall back to the defaults, so a
    plain-text request keeps working.
    """
    parts = getattr(message, 'parts', None)
    if parts:
        for payload in get_data_parts(parts):
            if not isinstance(payload, dict):
                continue
            try:
                context = AgentContext.model_validate(payload)
            except Exception:
                continue
            if context.current_location is not None:
                return context.current_location.latitude, context.current_location.longitude

    return default_lat, default_lng