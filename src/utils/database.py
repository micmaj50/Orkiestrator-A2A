import json
from typing import List, cast
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from FlagEmbedding import BGEM3FlagModel
import uuid
from utils.schema.Agent import A2AAgent


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
        The name of the best matching agent, or None if no matching point/payload is found.
    """


    model = _get_embedding_model()
    query_vector = model.encode([query_text])["dense_vecs"][0].tolist()

    response = client.query_points(
        collection_name="agent_skills", query=query_vector, limit=1
    )

    if response.points and response.points[0].payload:
        payload = response.points[0].payload
        return payload.get("agent_name") or payload.get("name")

    return None

def upload_agents_from_file(
    client: QdrantClient, file_path: str, collection_name: str = "agent_skills"
) -> None:

    """
    Load agent profiles from a JSON file, create embeddings, and upsert them to Qdrant.

    Parameters
    ----------
    client : QdrantClient
        Qdrant client instance.
    file_path : str
        Path to the JSON file containing agent definitions.
    collection_name : str, optional
        Target Qdrant collection name (default is "agent_skills").

    Returns
    -------
    Mone
    """

    
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )

    with open(file_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    model = _get_embedding_model()
    points = []

    for idx, item in enumerate(items):
        payload = item.get("payload", item)

        text = item.get("text_to_embed")
        if not text:
            name = payload.get("agent_name", payload.get("name", ""))
            desc = payload.get("descryption", payload.get("description", ""))
            skills = payload.get("sklills", payload.get("skills", []))
            text = f"{name} {desc} {' '.join(skills)}"

        vector = model.encode([text])["dense_vecs"][0].tolist()
        point_id = payload.get("agent_id", item.get("id", idx + 1))

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
        )

    client.upsert(collection_name=collection_name, points=points)

