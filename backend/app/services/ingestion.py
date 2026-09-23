"""
Ingestion pipeline (Graph-RAG hybrid context build):

  PDF/Text --> semantic chunking --> [Qdrant: embeddings]
                                  \-> [LLM extraction: entities/relations] --> Neo4j

Both stores are populated from the same chunk set so retrieval can later
join across them via `chunk_id` / `doc_id`.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from pypdf import PdfReader

from app.core.config import get_settings
from app.core.security import apply_input_guardrails
from app.schemas.models import ChunkRecord, GraphExtractionResult, IngestResponse
from app.services.graph_store import Neo4jGraphStore
from app.services.llm import complete_structured, embed_texts
from app.services.vector_store import QdrantVectorStore

settings = get_settings()

EXTRACTION_SYSTEM_PROMPT = """You are an information-extraction engine for an enterprise
knowledge graph. Given a chunk of document text, extract concrete named entities
(people, organizations, products, policies, metrics, systems) and directed
relationships between them. Only extract what is explicitly stated or strongly
implied by the text. Do not invent entities."""


def _read_text(source_path: str) -> str:
    path = Path(source_path)
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(errors="ignore")


def semantic_chunk(text: str, doc_id: str, chunk_size: int | None = None,
                    overlap: int | None = None) -> list[ChunkRecord]:
    """
    Sentence-aware sliding-window chunker. Splits on paragraph/sentence
    boundaries first, then packs into ~chunk_size windows with overlap so
    entity mentions near a boundary aren't lost.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    # crude sentence split; swap for a proper NLP sentence splitter in prod
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))

    chunks: list[ChunkRecord] = []
    current = ""
    idx = 0
    for sentence in sentences:
        if len(current) + len(sentence) > chunk_size and current:
            chunks.append(ChunkRecord(
                chunk_id=f"{doc_id}::chunk::{idx}", doc_id=doc_id,
                text=current.strip(), chunk_index=idx,
            ))
            # carry the tail `overlap` chars forward for continuity
            current = current[-overlap:] + " " + sentence
            idx += 1
        else:
            current += " " + sentence
    if current.strip():
        chunks.append(ChunkRecord(
            chunk_id=f"{doc_id}::chunk::{idx}", doc_id=doc_id, text=current.strip(), chunk_index=idx,
        ))
    return chunks


async def extract_graph_from_chunk(chunk_text: str) -> GraphExtractionResult:
    prompt = f"Extract entities and relationships from this text:\n\n\"\"\"\n{chunk_text}\n\"\"\""
    return await complete_structured(
        prompt=prompt, schema=GraphExtractionResult, system=EXTRACTION_SYSTEM_PROMPT,
    )


async def ingest_document(
    source_path: str,
    doc_id: str | None,
    metadata: dict,
    vector_store: QdrantVectorStore,
    graph_store: Neo4jGraphStore,
) -> IngestResponse:
    doc_id = doc_id or str(uuid.uuid4())
    raw_text = _read_text(source_path)

    chunks = semantic_chunk(raw_text, doc_id)
    if not chunks:
        return IngestResponse(doc_id=doc_id, num_chunks=0, num_entities=0,
                               num_relationships=0, status="failed")

    # --- Guardrail pass on every chunk before it's embedded/stored ---
    sanitized_chunks: list[ChunkRecord] = []
    for c in chunks:
        clean_text, flags = apply_input_guardrails(
            c.text, settings.ENABLE_PII_MASKING, settings.ENABLE_PROMPT_INJECTION_DETECTION
        )
        c.metadata["guardrail_flags"] = flags
        c.text = clean_text
        sanitized_chunks.append(c)

    # --- Vector store: embed + upsert ---
    vectors = await embed_texts([c.text for c in sanitized_chunks])
    await vector_store.upsert_chunks(
        ids=[c.chunk_id for c in sanitized_chunks],
        vectors=vectors,
        payloads=[
            {"chunk_id": c.chunk_id, "doc_id": doc_id, "text": c.text,
             "chunk_index": c.chunk_index, **metadata}
            for c in sanitized_chunks
        ],
    )

    # --- Graph store: entity/relationship extraction per chunk ---
    await graph_store.ensure_constraints()
    total_entities = total_relationships = 0
    for c in sanitized_chunks:
        await graph_store.upsert_chunk_node(c.chunk_id, doc_id, c.text, c.chunk_index)
        try:
            extraction = await extract_graph_from_chunk(c.text)
        except Exception:
            continue  # extraction failure on one chunk should not fail the whole ingest
        await graph_store.upsert_extraction(c.chunk_id, extraction.entities, extraction.relationships)
        total_entities += len(extraction.entities)
        total_relationships += len(extraction.relationships)

    return IngestResponse(
        doc_id=doc_id, num_chunks=len(sanitized_chunks),
        num_entities=total_entities, num_relationships=total_relationships,
        status="success",
    )
