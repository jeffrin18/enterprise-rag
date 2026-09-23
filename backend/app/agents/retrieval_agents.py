"""
Retrieval nodes. Each returns a partial AgentState update: `retrieved_chunks`
(and `subgraph` for the graph route), plus an explainability AgentStep.
"""
from __future__ import annotations

import re

from sqlalchemy import create_engine, text as sql_text

from app.agents.graph_state import AgentState, log_step
from app.core.config import get_settings
from app.schemas.models import GraphSubgraph, RetrievedChunk, RetrievalRoute
from app.services.graph_store import Neo4jGraphStore
from app.services.llm import embed_texts
from app.services.vector_store import QdrantVectorStore

settings = get_settings()

_vector_store = QdrantVectorStore()
_graph_store = Neo4jGraphStore()

_SQL_WRITE_GUARD = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH)\b", re.IGNORECASE)


async def vector_retrieval_node(state: AgentState) -> dict:
    query = state.get("rewritten_query") or state["question"]
    [vector] = await embed_texts([query])
    chunks = await _vector_store.search(vector, top_k=state.get("top_k", 6))
    return {
        "retrieved_chunks": chunks,
        **log_step("vector_retrieval", "Executing Vector Search", "success",
                    f"{len(chunks)} chunks retrieved from Qdrant"),
    }


async def graph_retrieval_node(state: AgentState) -> dict:
    cypher = state.get("cypher_query")
    if cypher:
        try:
            records = await _graph_store.run_readonly_cypher(cypher)
            chunks = [
                RetrievedChunk(
                    chunk_id=r.get("chunk_id", f"graph_{i}"),
                    text=str(r.get("text") or r),
                    score=1.0, source=RetrievalRoute.GRAPH, metadata=r,
                )
                for i, r in enumerate(records)
            ]
            return {
                "retrieved_chunks": chunks,
                **log_step("graph_retrieval", "Executing Cypher", "success",
                            f"Cypher returned {len(records)} rows"),
            }
        except ValueError as e:
            # Rejected write clause (Cypher-injection guardrail) — fall back safely.
            return {
                "retrieved_chunks": [],
                **log_step("graph_retrieval", "Executing Cypher", "error", str(e)),
            }

    # No LLM-authored Cypher (or it failed) -> fall back to entity-anchored traversal
    naive_entities = [w.strip(",.?!") for w in state["question"].split() if w[:1].isupper()]
    chunks, subgraph = await _graph_store.graph_traversal_search(naive_entities or [state["question"]])
    return {
        "retrieved_chunks": chunks, "subgraph": subgraph,
        **log_step("graph_retrieval", "Executing Cypher", "success",
                    f"Fallback traversal found {len(subgraph.nodes)} nodes"),
    }


async def sql_retrieval_node(state: AgentState) -> dict:
    sql = state.get("sql_query")
    if not sql or _SQL_WRITE_GUARD.search(sql):
        return {
            "retrieved_chunks": [],
            **log_step("sql_retrieval", "Executing SQL", "error",
                        "No safe SELECT-only query available"),
        }
    engine = create_engine(settings.SQL_DATABASE_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql_text(sql)).mappings().all()
    except Exception as e:
        return {"retrieved_chunks": [],
                **log_step("sql_retrieval", "Executing SQL", "error", str(e))}

    chunks = [
        RetrievedChunk(chunk_id=f"sql_{i}", text=str(dict(row)), score=1.0,
                        source=RetrievalRoute.SQL, metadata=dict(row))
        for i, row in enumerate(rows)
    ]
    return {
        "retrieved_chunks": chunks,
        **log_step("sql_retrieval", "Executing SQL", "success", f"{len(chunks)} rows returned"),
    }


async def hybrid_retrieval_node(state: AgentState) -> dict:
    vector_update = await vector_retrieval_node(state)
    graph_update = await graph_retrieval_node(state)
    merged_chunks = vector_update.get("retrieved_chunks", []) + graph_update.get("retrieved_chunks", [])
    return {
        "retrieved_chunks": merged_chunks,
        "subgraph": graph_update.get("subgraph", GraphSubgraph()),
        "agent_steps": vector_update["agent_steps"] + graph_update["agent_steps"],
    }
