"""Fictional agents used to fill the vector database.

Nothing runs in the background - they simply provide a realistic number of entries to search through.
"""

import json
from pathlib import Path
from a2a.types import AgentCard


def load_mock_agent_cards() -> list[AgentCard]:
    json_path = Path(__file__).parent / "mock_cards.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return [AgentCard(**card) for card in data]


MOCK_AGENT_CARDS: list[AgentCard] = load_mock_agent_cards()
