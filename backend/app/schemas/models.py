"""
Pydantic schemas.

These serve two purposes:
1. API request/response contracts (FastAPI).
2. Structured-output contracts that every LLM call is forced through
   (via `instructor`-style function calling / JSON mode), guaranteeing
   zero JSON structural failures downstream.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------

class IngestRequest(BaseModel):
    source_path: str = Field(..., description="Path or URI of the document to ingest")
    doc_id: Optional[str] = Field(None, description="Stable external id; generated if absent")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkRecord(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedEntity(BaseModel):
    name: str
    type: str = Field(..., description="e.g. PERSON, ORG, PRODUCT, POLICY, METRIC")
    description: Optional[str] = None


class ExtractedRelationship(BaseModel):
    source: str
    target: str
    relation: str = Field(..., description="Verb phrase, e.g. ACQUIRED, REPORTS_TO, DEFINED_IN")
    evidence: Optional[str] = Field(None, description="Supporting chunk text span")


class GraphExtractionResult(BaseModel):
    """Forced structured output of the entity/relationship extraction LLM call."""
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)

    @field_validator("relationships")
    @classmethod
    def relationships_reference_known_entities(cls, v, info):
        # Soft validation: filter out relationships that reference nothing usable
        return [r for r in v if r.source and r.target and r.relation]


class IngestResponse(BaseModel):
    doc_id: str
    num_chunks: int
    num_entities: int
    num_relationships: int
    status: Literal["success", "partial", "failed"]


# --------------------------------------------------------------------------
# Query / Routing
# --------------------------------------------------------------------------

class RetrievalRoute(str, Enum):
    VECTOR = "vector_search"
    GRAPH = "graph_traversal"
    SQL = "structured_sql"
    HYBRID = "hybrid"


class RouterDecision(BaseModel):
    """Forced structured output of the Router Agent."""
    route: RetrievalRoute
    reasoning: str = Field(..., description="Short rationale for the routing decision")
    cypher_query: Optional[str] = Field(None, description="Populated if route == graph_traversal")
    sql_query: Optional[str] = Field(None, description="Populated if route == structured_sql")
    rewritten_query: Optional[str] = Field(None, description="Query rewritten for retrieval quality")


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    source: RetrievalRoute
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class GraphSubgraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    top_k: int = Field(6, ge=1, le=25)


# --------------------------------------------------------------------------
# Critique / Self-correction
# --------------------------------------------------------------------------

class CritiqueVerdict(BaseModel):
    """Forced structured output of the Critique Agent."""
    faithfulness_score: float = Field(..., ge=0.0, le=1.0)
    context_recall_score: float = Field(..., ge=0.0, le=1.0)
    hallucination_detected: bool
    missing_information: list[str] = Field(default_factory=list)
    verdict: Literal["accept", "retry"]
    retry_instructions: Optional[str] = Field(
        None, description="If verdict == retry: how the next retrieval pass should differ"
    )


class AgentStep(BaseModel):
    """One node execution in the LangGraph run, surfaced to the UI for explainability."""
    step: str
    label: str
    status: Literal["running", "success", "warning", "error"]
    detail: Optional[str] = None
    timestamp: float


class QueryResponse(BaseModel):
    answer: str
    session_id: Optional[str] = None
    route_taken: RetrievalRoute
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    subgraph: GraphSubgraph = GraphSubgraph()
    critique: Optional[CritiqueVerdict] = None
    agent_steps: list[AgentStep] = Field(default_factory=list)
    self_corrections: int = 0
    guardrail_flags: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Evaluation (Ragas)
# --------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    question: str
    answer: str
    contexts: list[str]
    ground_truth: Optional[str] = None


class EvaluateResponse(BaseModel):
    faithfulness: float
    answer_relevancy: float
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    passed: bool
