from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.models import IngestRequest, IngestResponse
from app.services.graph_store import Neo4jGraphStore
from app.services.ingestion import ingest_document
from app.services.vector_store import QdrantVectorStore

router = APIRouter(prefix="/ingest", tags=["ingest"])

_vector_store = QdrantVectorStore()
_graph_store = Neo4jGraphStore()


@router.post("", response_model=IngestResponse)
async def ingest(request: IngestRequest) -> IngestResponse:
    try:
        return await ingest_document(
            source_path=request.source_path,
            doc_id=request.doc_id,
            metadata=request.metadata,
            vector_store=_vector_store,
            graph_store=_graph_store,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Source not found: {request.source_path}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
