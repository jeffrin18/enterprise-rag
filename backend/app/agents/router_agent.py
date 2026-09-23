"""
Router Agent: classifies query intent and picks the retrieval strategy.

- VECTOR   -> semantic / "explain", "summarize", "what does X say about Y"
- GRAPH    -> relational / "who reports to", "how is X connected to Y",
              multi-hop questions
- SQL      -> aggregate / numeric questions over structured tables
- HYBRID   -> ambiguous, needs both vector context and graph relations
"""
from __future__ import annotations

from app.agents.graph_state import AgentState, log_step
from app.schemas.models import RouterDecision
from app.services.llm import complete_structured

ROUTER_SYSTEM_PROMPT = """You are the Router Agent in an enterprise RAG system with three
retrieval backends:
- vector_search: unstructured semantic search over document chunks (Qdrant)
- graph_traversal: Neo4j knowledge graph of entities/relationships extracted from documents;
  use for multi-hop, relational, "how is X connected to Y" questions. If you choose this route,
  also emit a READ-ONLY Cypher query (MATCH ... RETURN ..., no CREATE/MERGE/DELETE/SET).
- structured_sql: numeric/aggregate lookups over a structured table named `metrics`
  with columns (id, entity, metric_name, value, period). If you choose this route, emit
  a SELECT-only SQL query.

Pick the single best route (or hybrid if the question clearly needs both semantic context
and explicit relationships). Always also produce a `rewritten_query`: a clearer, more
retrieval-friendly restatement of the user's question."""


async def router_node(state: AgentState) -> dict:
    decision: RouterDecision = await complete_structured(
        prompt=f"User question: {state['question']}",
        schema=RouterDecision,
        system=ROUTER_SYSTEM_PROMPT,
    )
    return {
        "route": decision.route,
        "rewritten_query": decision.rewritten_query or state["question"],
        "cypher_query": decision.cypher_query,
        "sql_query": decision.sql_query,
        **log_step("router", "Routing Query", "success",
                    f"Route={decision.route.value}: {decision.reasoning}"),
    }


def route_selector(state: AgentState) -> str:
    """Conditional-edge function: maps the decided route to the next node name."""
    route = state["route"]
    mapping = {
        "vector_search": "vector_retrieval",
        "graph_traversal": "graph_retrieval",
        "structured_sql": "sql_retrieval",
        "hybrid": "hybrid_retrieval",
    }
    return mapping.get(route.value if hasattr(route, "value") else route, "vector_retrieval")
