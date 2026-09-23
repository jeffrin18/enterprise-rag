"""
Shared state object threaded through every LangGraph node.
"""
from __future__ import annotations

import time
from typing import Annotated, Any, Optional, TypedDict

from app.schemas.models import (
    AgentStep, CritiqueVerdict, GraphSubgraph, RetrievalRoute, RetrievedChunk,
)


def _append(left: list, right: list) -> list:
    return left + right


class AgentState(TypedDict, total=False):
    # input
    question: str
    session_id: Optional[str]
    top_k: int

    # guardrails
    guardrail_flags: Annotated[list[str], _append]
    blocked: bool

    # routing
    route: RetrievalRoute
    rewritten_query: str
    cypher_query: Optional[str]
    sql_query: Optional[str]

    # retrieval
    retrieved_chunks: list[RetrievedChunk]
    subgraph: GraphSubgraph

    # generation + critique
    answer: str
    critique: Optional[CritiqueVerdict]
    self_corrections: int

    # explainability trail surfaced to the frontend
    agent_steps: Annotated[list[AgentStep], _append]


def log_step(step: str, label: str, status: str, detail: str = "") -> dict:
    return {"agent_steps": [AgentStep(step=step, label=label, status=status,
                                       detail=detail, timestamp=time.time())]}
