"""
Qdrant vector store wrapper. Isolated behind a small interface so swapping
to Pinecone means editing only this file (see PineconeVectorStore stub below).
"""
from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings
from app.schemas.models import RetrievedChunk, RetrievalRoute

settings = get_settings()


class QdrantVectorStore:
    def __init__(self):
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
        self.collection = settings.QDRANT_COLLECTION

    async def ensure_collection(self):
        collections = await self.client.get_collections()
        names = {c.name for c in collections.collections}
        if self.collection not in names:
            await self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=settings.EMBEDDING_DIM, distance=models.Distance.COSINE
                ),
            )

    async def upsert_chunks(
        self, ids: list[str], vectors: list[list[float]], payloads: list[dict[str, Any]]
    ) -> None:
        await self.ensure_collection()
        points = [
            models.PointStruct(id=self._point_id(i), vector=v, payload=p)
            for i, v, p in zip(ids, vectors, payloads)
        ]
        await self.client.upsert(collection_name=self.collection, points=points)

    async def search(self, query_vector: list[float], top_k: int = 6,
                      filters: dict[str, Any] | None = None) -> list[RetrievedChunk]:
        await self.ensure_collection()
        qfilter = None
        if filters:
            qfilter = models.Filter(
                must=[models.FieldCondition(key=k, match=models.MatchValue(value=v))
                      for k, v in filters.items()]
            )
        results = await self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qfilter,
        )
        return [
            RetrievedChunk(
                chunk_id=str(r.payload.get("chunk_id", r.id)),
                text=r.payload.get("text", ""),
                score=float(r.score),
                source=RetrievalRoute.VECTOR,
                metadata={k: v for k, v in r.payload.items() if k not in ("text", "chunk_id")},
            )
            for r in results
        ]

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        # Qdrant point ids must be UUID or unsigned int; derive a stable UUID from chunk_id.
        return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


# --------------------------------------------------------------------------
# Alternative backend: Pinecone (swap-in). Kept minimal / illustrative.
# --------------------------------------------------------------------------

class PineconeVectorStore:
    def __init__(self):
        from pinecone import Pinecone
        self.pc = Pinecone(api_key=settings.__dict__.get("PINECONE_API_KEY", ""))
        self.index = self.pc.Index(settings.QDRANT_COLLECTION)

    async def upsert_chunks(self, ids, vectors, payloads):
        self.index.upsert(vectors=[(i, v, p) for i, v, p in zip(ids, vectors, payloads)])

    async def search(self, query_vector, top_k=6, filters=None):
        res = self.index.query(vector=query_vector, top_k=top_k, include_metadata=True, filter=filters)
        return [
            RetrievedChunk(
                chunk_id=m["id"], text=m["metadata"].get("text", ""),
                score=m["score"], source=RetrievalRoute.VECTOR, metadata=m["metadata"],
            )
            for m in res["matches"]
        ]


def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore()
