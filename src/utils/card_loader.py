import json
from pathlib import Path
from a2a.types import AgentCard


def load_agent_card(json_path: Path, agent_url: str | None = None) -> AgentCard:
    """Loads the AgentCard structure from a JSON file and optionally overrides the URL."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    
    card = AgentCard(**data)

    if agent_url and card.supported_interfaces:
        card.supported_interfaces[0].url = agent_url

    return card