import sys
import json
from pathlib import Path
import pytest

from agents.registry import AgentDiscoveryError, discover_agents

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))


def _write_card(root: Path, agent_key: str, url: str) -> None:
    agent_dir = root / agent_key
    agent_dir.mkdir()
    (agent_dir / "app.py").write_text(
        "def create_executor():\n"
        "    raise NotImplementedError\n",
        encoding="utf-8"
    )
    (agent_dir / "card.json").write_text(
        json.dumps(
            {
                "name": agent_key,
                "supported_interfaces": [{"url": url}]
            }
        ),
        encoding="utf-8"
    )


def test_discovers_cards_in_deterministic_order(tmp_path: Path) -> None:
    _write_card(tmp_path, "weather_agent", "http://127.0.0.1:9995")
    _write_card(tmp_path, "food_agent", "http://127.0.0.1:9997")
    (tmp_path / "not_an_agent").mkdir()

    agents = discover_agents(tmp_path)

    assert [agent.key for agent in agents] == ["food_agent", "weather_agent"]
    assert agents[0].route == "food"
    assert agents[0].mount_path == "/food"
    assert agents[0].default_url == "http://127.0.0.1:9997"


def test_rejects_duplicate_derived_routes(tmp_path: Path) -> None:
    _write_card(tmp_path, "food", "http://127.0.0.1:9001")
    _write_card(tmp_path, "food_agent", "http://127.0.0.1:9002")

    with pytest.raises(AgentDiscoveryError, match="Duplicate agent route"):
        discover_agents(tmp_path)


def test_rejects_card_without_interface(tmp_path: Path) -> None:
    agent_dir = tmp_path / "food_agent"
    agent_dir.mkdir()
    (agent_dir / "app.py").write_text("", encoding="utf-8")
    (agent_dir / "card.json").write_text(
        json.dumps({"name": "Food Agent"}),
        encoding="utf-8"
    )
    with pytest.raises(AgentDiscoveryError, match="Invalid agent card"):
        discover_agents(tmp_path)

def test_rejects_card_without_app_module(tmp_path: Path) -> None:
    agent_dir = tmp_path / "food_agent"
    agent_dir.mkdir()
    (agent_dir / "card.json").write_text(
        json.dumps(
            {
                "name": "Food Agent",
                "supported_interfaces": [
                    {"url": "http://127.0.0.1:9997"}
                ]
            }
        ),
        encoding="utf-8"
    )
    with pytest.raises(AgentDiscoveryError, match="Invalid agent setup"):
        discover_agents(tmp_path)