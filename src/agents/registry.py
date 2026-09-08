"""Filesystem-based discovery for local A2A agents.

An agent opts in by providing `agents/<agent_key>/card.json`.
"""

import json
from pathlib import Path
from urllib.parse import urlsplit


AGENTS_ROOT = Path(__file__).resolve().parent
ORCHESTRATOR_KEY = "orchestrator"


class AgentDiscoveryError(RuntimeError):
    """Raised when discovered agent does not satisfy the local contract."""


class AgentDefinition:
    """Local runtime information derived from an agent directory and card."""

    def __init__(
        self,
        key: str,
        card_path: Path,
        default_url: str
    ) -> None:
        self.key = key
        self.route = key.removesuffix("_agent")
        self.card_path = card_path
        self.default_url = default_url
        self.mount_path = f"/{self.route}"
        self.env_prefix = key.upper()
        self.is_orchestrator = key == ORCHESTRATOR_KEY


def _read_default_url(card_path: Path) -> str:
    try:
        data = json.loads(card_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError

        interfaces = data.get("supported_interfaces") or data.get("supportedInterfaces")
        default_url = interfaces[0]["url"]

        parsed_url = urlsplit(default_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError

        return default_url.rstrip("/")

    except(OSError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise AgentDiscoveryError(f"Invalid agent card: {card_path}") from exc


def discover_agents(agents_root: Path = AGENTS_ROOT) -> list[AgentDefinition]:
    """ Discover agents that expose `card.json` file"""

    definitions: list[AgentDefinition] = []
    routes: set[str] = set()

    for card_path in sorted(agents_root.glob("*/card.json")):
        directory = card_path.parent
        agent_key = directory.name
        route = agent_key.removesuffix("_agent")

        if not agent_key.isidentifier() or not route or not (directory / "app.py").is_file():
            raise AgentDiscoveryError(f"Invalid agent setup: {directory}")

        if route in routes:
            raise AgentDiscoveryError(f"Duplicate agent route: /{route}")
        routes.add(route)

        definitions.append(
            AgentDefinition(
                key=agent_key,
                card_path=card_path,
                default_url=_read_default_url(card_path)
            )
        )
    return definitions

def get_agent_definition(agent_key: str) -> AgentDefinition:
    """Return one discovered agent."""

    for definition in discover_agents():
        if definition.key == agent_key:
            return definition

    raise AgentDiscoveryError(f"Unknown agent: {agent_key}")

