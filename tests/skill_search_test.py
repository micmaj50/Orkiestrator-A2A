"""Tests for the floor under the agent lookup.

The vector search returns its nearest hit however far away it is. That turned a
request no agent covers into a confident answer from whichever agent happened
to be closest, so the search now carries a minimum score.
"""

from types import SimpleNamespace

import numpy
import pytest

from utils import database


class FakeQdrant:
    """Replaces the client, dropping hits below the threshold the way Qdrant does."""

    def __init__(self, *scores):
        self.scores = scores
        self.received_threshold = None

    def query_points(self, collection_name, query, limit, score_threshold=None):
        kept = [
            SimpleNamespace(score=score, payload={'agent_name': 'gas_agent'})
            for score in self.scores if score >= score_threshold
        ]
        self.received_threshold = score_threshold

        return SimpleNamespace(points=kept[:limit])


@pytest.fixture(autouse=True)
def no_embedding_model(monkeypatch):
    """The real model is a download, and the vector it returns is irrelevant here."""

    # The real model returns numpy rows, and the caller calls .tolist().
    fake = SimpleNamespace(encode=lambda texts: {'dense_vecs': numpy.zeros((1, 1024))})
    monkeypatch.setattr(database, '_get_embedding_model', lambda: fake)


def test_the_threshold_reaches_the_search(monkeypatch):
    """
    Qdrant does the filtering, so dropping the argument would disable the floor
    without any other test noticing.
    """

    monkeypatch.setenv('MIN_SKILL_SCORE', '0.42')
    client = FakeQdrant(0.9)

    database.search_skill(client, 'find fuel')

    assert client.received_threshold == 0.42


@pytest.mark.parametrize(('score', 'expected'), [
    (0.81, 'gas_agent'),
    # `tell me a joke` used to come back as the nearest agent and get answered.
    (0.21, None),
])
def test_only_a_close_enough_skill_is_matched(monkeypatch, score, expected):
    monkeypatch.setenv('MIN_SKILL_SCORE', '0.5')

    assert database.search_skill(FakeQdrant(score), 'find fuel') == expected


def test_the_threshold_is_tunable_without_a_code_change(monkeypatch):
    """Calibration is an env change, because the right value comes from real traffic."""

    monkeypatch.setenv('MIN_SKILL_SCORE', '0.5')
    assert database.search_skill(FakeQdrant(0.55), 'find fuel') == 'gas_agent'

    monkeypatch.setenv('MIN_SKILL_SCORE', '0.6')
    assert database.search_skill(FakeQdrant(0.55), 'find fuel') is None
