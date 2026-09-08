import json
from pathlib import Path
import asyncio

from agents import remote_registry
from agents.remote_registry import (
    load_remote_agent_configs,
    RemoteAgentConfig,
    fetch_remote_agent_cards
)


def write_database(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def tests_loads_enabled_remote_agents(tmp_path: Path) -> None:
    database_path = tmp_path / "database.json"
    write_database(
        database_path,
        {
            "remote_agents": [
                {
                    "key": "weather_remote",
                    "base_url": "https://weather.example.com"
                },
                {
                    "key": "disabled_agent",
                    "base_url": "https://disabled.example.com",
                    "enabled": False
                }
            ]
        }
    )

    agents, errors = load_remote_agent_configs(database_path)

    assert errors == []
    assert [agent.key for agent in agents] == ["weather_remote"]
    assert str(agents[0].base_url) == "https://weather.example.com/"


def test_invalid_entry_does_not_block_valid_entries(tmp_path: Path) -> None:
    database_path = tmp_path / "database.json"
    write_database(
        database_path,
        {
            "remote_agents": [
                {
                    "key": "weather_remote",
                    "base_url": "https://weather.example.com"
                },
                {
                    "key": "invalid_agent",
                    "base_url": "not-url"
                }
            ]
        }
    )

    agents, errors = load_remote_agent_configs(database_path)

    assert [agent.key for agent in agents] == ["weather_remote"]
    assert len(errors) == 1
    assert errors[0].startswith("Invalid remote agent entry 2:")


def test_rejects_old_list_format(tmp_path: Path) -> None:
    database_path = tmp_path / "database.json"
    write_database(database_path, [])

    agents, errors = load_remote_agent_configs(database_path)

    assert agents == []
    assert errors == ["database.json must contain a JSON object"]


def test_requires_remote_agents_list(tmp_path: Path) -> None:
    database_path = tmp_path / "database.json"
    write_database(database_path, {})
    
    agents, errors = load_remote_agent_configs(database_path)
    
    assert agents == []
    assert errors == ["database.json must contain a remote_agents list"]


def test_reports_invalid_json(tmp_path: Path) -> None:
    database_path = tmp_path / "database.json"
    database_path.write_text("{invalid", encoding="utf-8")
    
    agents, errors = load_remote_agent_configs(database_path)
    
    assert agents == []
    assert len(errors) == 1
    assert errors[0].startswith("Could not load remote agent configuration:")


def test_reports_missing_database_file(tmp_path: Path) -> None:
    database_path = tmp_path / "missing.json"
    
    agents, errors = load_remote_agent_configs(database_path)
    
    assert agents == []
    assert len(errors) == 1
    assert errors[0].startswith("Could not load remote agent configuration:")


class FakeCardResolver:
    def __init__(self, httpx_client, base_url: str):
        self.base_url = base_url

    async def get_agent_card(self):
        if "unavailable" in self.base_url:
            raise RuntimeError("endpoint unavailable")

        if "slow" in self.base_url:
            await asyncio.sleep(1)

        return self.base_url


def test_fetches_remote_agent_cards(monkeypatch) -> None:
    monkeypatch.setattr(remote_registry, "A2ACardResolver", FakeCardResolver)
    configs = [
        RemoteAgentConfig(
            key="weather_remote",
            base_url="https://weather.example.com"
        )
    ]

    cards, errors = asyncio.run(fetch_remote_agent_cards(configs))

    assert errors == []
    assert cards == {"weather_remote": "https://weather.example.com"}


def test_unavailable_agent_does_not_block_other_agents(monkeypatch) -> None:
    monkeypatch.setattr(remote_registry, "A2ACardResolver", FakeCardResolver)
    configs = [
        RemoteAgentConfig(
            key="unavailable_agent",
            base_url="https://unavailable.example.com"
        ),
        RemoteAgentConfig(
            key="weather_remote",
            base_url="https://weather.example.com"
        )
    ]

    cards, errors = asyncio.run(fetch_remote_agent_cards(configs))

    assert cards == {"weather_remote": "https://weather.example.com"}
    assert len(errors) == 1
    assert "unavailable_agent" in errors[0]


def test_reports_agent_card_timeout(monkeypatch) -> None:
    monkeypatch.setattr(remote_registry, "A2ACardResolver", FakeCardResolver)
    configs = [
        RemoteAgentConfig(
            key="slow_agent",
            base_url="https://slow.example.com"
        )
    ]

    cards, errors = asyncio.run(fetch_remote_agent_cards(configs, timeout_seconds=0.01))

    assert cards == {}
    assert len(errors) == 1
    assert "timed out" in errors[0]


def test_duplicate_remote_agent_key_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(remote_registry, "A2ACardResolver", FakeCardResolver)
    configs = [
        RemoteAgentConfig(
            key="weather_remote",
            base_url="https://first.example.com"
        ),
        RemoteAgentConfig(
            key="weather_remote",
            base_url="https://second.example.com"
        )
    ]

    cards, errors = asyncio.run(fetch_remote_agent_cards(configs))

    assert cards == {"weather_remote": "https://first.example.com"}
    assert errors == ["Duplicate remote agent key: weather_remote"]
