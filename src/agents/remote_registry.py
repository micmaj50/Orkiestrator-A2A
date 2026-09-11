import json
from pathlib import Path
from pydantic import AnyHttpUrl, BaseModel, ValidationError
import asyncio
import httpx
from a2a.client import A2ACardResolver
from a2a.types import AgentCard

from config import get_external_api_timeout_seconds


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "database.json"


class RemoteAgentConfig(BaseModel):
    """Configuration required to discover a remote A2A agent."""

    key: str
    base_url: AnyHttpUrl
    enabled: bool = True


def load_remote_agent_configs(
    database_path: str | Path = DEFAULT_DATABASE_PATH
) -> tuple[list[RemoteAgentConfig], list[str]]:
    """Load valid remote agent entries and report invalid ones."""

    path = Path(database_path)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"Could not load remote agent configuration: {exc}"]

    if not isinstance(data, dict):
        return [], ["database.json must contain a JSON object"]

    entries = data.get("remote_agents")
    if not isinstance(entries, list):
        return [], ["database.json must contain a remote_agents list"]

    agents: list[RemoteAgentConfig] = []
    errors: list[str] = []

    for index, entry in enumerate(entries, start=1):
        try:
            agent = RemoteAgentConfig.model_validate(entry)
        except ValidationError as exc:
            errors.append(f"Invalid remote agent entry {index}: {exc}")
            continue
            
        if agent.enabled:
            agents.append(agent)

    return agents, errors


async def fetch_remote_agent_cards(
    agents: list[RemoteAgentConfig],
    timeout_seconds: float | None = None
) -> tuple[dict[str, AgentCard], list[str]]:
    """Fetch remote Agent Cards without letting one failure stop the others."""

    unique_agents: list[RemoteAgentConfig] = []
    seen_keys: set[str] = set()
    errors: list[str] = []

    for agent in agents:
        if agent.key in seen_keys:
            errors.append(f"Duplicate remote agent key: {agent.key}")
            continue

        seen_keys.add(agent.key)
        unique_agents.append(agent)

    if not unique_agents:
        return {}, errors

    timeout = timeout_seconds if timeout_seconds is not None else get_external_api_timeout_seconds()

    async with httpx.AsyncClient(timeout=timeout) as client:
        requests = [
            asyncio.wait_for(
                A2ACardResolver(
                    httpx_client=client,
                    base_url=str(agent.base_url).rstrip("/")
                ).get_agent_card(),
                timeout=timeout
            )
            for agent in unique_agents
        ]
        results = await asyncio.gather(*requests, return_exceptions=True)

    cards: dict[str, AgentCard] = {}

    for agent, result in zip(unique_agents, results, strict=True):
        if isinstance(result, (TimeoutError, httpx.TimeoutException)):
            errors.append(f"Remote agent '{agent.key}' timed out")
        elif isinstance(result, Exception):
            errors.append(f"Could not load remote agent '{agent.key}': {result}")
        else:
            cards[agent.key] = result

    return cards, errors
