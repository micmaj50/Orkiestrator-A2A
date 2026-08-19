from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams,PointStruct,Filter, FieldCondition, MatchValue

class A2AAgent(BaseModel):
    agent_id: int
    name: str
    url: HttpUrl
    keywords :str
    descryption: str
    sklills: List[str]



if __name__ == '__main__':
    client = QdrantClient(":memory:")    

    client.create_collection(
    collection_name="my_documents",
    vectors_config=VectorParams(size=4, distance=Distance.COSINE),
    )


    client.upsert(
        collection_name="my_documents",
        points=[
            PointStruct(
                id=1,
                vector=[0.05, 0.61, -0.23, 0.12],
                payload={"category": "tech", "title": "Vector DB Overview"}
            ),
            PointStruct(
                id=2,
                vector=[0.89, -0.11, 0.44, 0.03],
                payload={"category": "cooking", "title": "Pasta Recipe"}
            ),
                        PointStruct(
                id=3,
                vector=[0.90, -0.10, 0.45, 0.02],
                payload={"category": "cooking", "title": "Serniczek"}
            ),
        ]
    )


    search_result = client.query_points(
    collection_name="my_documents",
    query=[0.89, -0.11, 0.46, 0.02], 
    query_filter=Filter(
        must=[
            FieldCondition(
                key="category",
                match=MatchValue(value="cooking")
            )
        ]
    ),
    limit=1
)

    for hit in search_result.points:
        print(f"ID: {hit.id}, Score: {hit.score}, Metadata: {hit.payload}")