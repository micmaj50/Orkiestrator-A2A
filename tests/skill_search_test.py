"""Tests for the floor under the agent lookup.

The vector search always returns its nearest hit, however far away it is. That
turned a request no agent covers into a confident answer from whichever agent
happened to be closest, so there is a minimum score now.
"""

import numpy
import pytest

import config
from utils import database


class FakePoint:
    def __init__(self, score, agent_name='gas_agent'):
        self.score = score
        self.payload = {'agent_name': agent_name} if agent_name else None


class FakeResponse:
    def __init__(self, points):
        self.points = points


class FakeQdrant:
    """Replaces the client: these tests are about the threshold, not the search."""

    def __init__(self, points):
        self.response = FakeResponse(points)

    def query_points(self, collection_name, query, limit):
        return self.response


@pytest.fixture(autouse=True)
def no_embedding_model(monkeypatch):
    """The real model is a download; the vector it returns is irrelevant here."""

    class FakeModel:
        def encode(self, texts):
            # The real model returns numpy rows, and the caller calls .tolist().
            return {'dense_vecs': numpy.zeros((1, 1024))}

    monkeypatch.setattr(database, '_get_embedding_model', FakeModel)


def test_a_close_enough_skill_is_matched(monkeypatch):
    monkeypatch.setenv('MIN_SKILL_SCORE', '0.5')

    client = FakeQdrant([FakePoint(0.81)])

    assert database.search_skill(client, 'where can I refuel') == 'gas_agent'


def test_a_distant_skill_is_no_match(monkeypatch):
    """`tell me a joke` used to come back as the nearest agent and get answered."""

    monkeypatch.setenv('MIN_SKILL_SCORE', '0.5')

    client = FakeQdrant([FakePoint(0.21)])

    assert database.search_skill(client, 'tell me a joke') is None


def test_the_threshold_is_tunable_without_a_code_change(monkeypatch):
    """Calibration is an env change, because the right value comes from real traffic."""

    client = FakeQdrant([FakePoint(0.55)])

    monkeypatch.setenv('MIN_SKILL_SCORE', '0.5')
    assert database.search_skill(client, 'find fuel') == 'gas_agent'

    monkeypatch.setenv('MIN_SKILL_SCORE', '0.6')
    assert database.search_skill(client, 'find fuel') is None


def test_a_hit_without_a_payload_is_no_match(monkeypatch):
    monkeypatch.setenv('MIN_SKILL_SCORE', '0.5')

    client = FakeQdrant([FakePoint(0.9, agent_name=None)])

    assert database.search_skill(client, 'find fuel') is None


def test_an_empty_index_is_no_match():
    assert database.search_skill(FakeQdrant([]), 'find fuel') is None


def test_the_default_threshold_is_read_from_the_environment(monkeypatch):
    monkeypatch.delenv('MIN_SKILL_SCORE', raising=False)
    assert config.get_min_skill_score() == 0.5

    monkeypatch.setenv('MIN_SKILL_SCORE', '0.72')
    assert config.get_min_skill_score() == 0.72
