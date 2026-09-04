from a2a.types import AgentCard, AgentSkill
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from FlagEmbedding import BGEM3FlagModel

from config import get_min_skill_score


COLLECTION_NAME = "agent_skills"

_EMBEDDING_MODEL: BGEM3FlagModel | None = None

def _get_embedding_model() -> BGEM3FlagModel:

    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        _EMBEDDING_MODEL = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
    return _EMBEDDING_MODEL


def search_skill(client: QdrantClient, query_text: str) -> str | None:
    """
    Perform semantic search in Qdrant to find the single most relevant agent.
    Parameters
    ----------
    client : QdrantClient
        The Qdrant client instance.
    query_text : str
        Task from LLM

    Returns
    -------
    str | None
        The name of the best matching agent, or None when nothing is close
        enough to count as a match.
    """


    model = _get_embedding_model()
    query_vector = model.encode([query_text])["dense_vecs"][0].tolist()

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=1,
    )

    if not response.points:
        return None

    best = response.points[0]
    agent_name = best.payload.get("agent_name") if best.payload else None
    minimum = get_min_skill_score()

    # The search returns its nearest hit however far away it is, so a request
    # no agent covers would otherwise be handed to whichever one was closest.
    # Both branches log the score: that is the data the threshold is tuned on.
    if agent_name is None or best.score < minimum:
        print(f'search_skill: {query_text!r} -> no match (nearest {agent_name} at {best.score:.3f}, minimum {minimum})')
        return None

    print(f'search_skill: {query_text!r} -> {agent_name} ({best.score:.3f})')

    return agent_name



def _skill_to_text(card: AgentCard, skill: AgentSkill) -> str:
    tags = ". ".join(skill.tags or [])

    skill_text = (
        f"Agent: {card.name}\n"
        f"Agent description: {card.description}\n"
        f"Skill: {skill.name}\n"
        f"Skill description: {skill.description}\n"
        f"Tags: {tags}\n"
    )

    return [skill_text, *(skill.examples or [])]


def upload_agents_cards(client: QdrantClient, agent_cards: dict[str, AgentCard]) -> None:
    """Build Qdrant skill index from discovered A2A agent cards."""

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
        )

    model = _get_embedding_model()
    points = []
    point_id = 1

    for agent_name, card in sorted(agent_cards.items()):
        for skill in card.skills or []:
            for text in _skill_to_text(card, skill):
                vector = model.encode([text])["dense_vecs"][0].tolist()

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "agent_name": agent_name,
                            "skill_id": skill.id
                        }
                    )
                )
                point_id += 1

    if points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )