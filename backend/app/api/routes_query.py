from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.workflow import run_query_workflow
from app.core.config import get_settings
from app.core.security import apply_input_guardrails
from app.schemas.models import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["query"])
settings = get_settings()


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    # Guardrail pass BEFORE the question reaches any agent or LLM call.
    sanitized_question, flags = apply_input_guardrails(
        request.question, settings.ENABLE_PII_MASKING, settings.ENABLE_PROMPT_INJECTION_DETECTION
    )
    if any(f.startswith("prompt_injection_suspected") for f in flags):
        raise HTTPException(
            status_code=400,
            detail="Query blocked: potential prompt injection detected. Please rephrase your question.",
        )

    try:
        final_state = await run_query_workflow(
            question=sanitized_question, session_id=request.session_id, top_k=request.top_k,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Query workflow failed: {e}")

    return QueryResponse(
        answer=final_state.get("answer", ""),
        session_id=request.session_id,
        route_taken=final_state.get("route"),
        retrieved_chunks=final_state.get("retrieved_chunks", []),
        subgraph=final_state.get("subgraph") or {"nodes": [], "edges": []},
        critique=final_state.get("critique"),
        agent_steps=final_state.get("agent_steps", []),
        self_corrections=final_state.get("self_corrections", 0),
        guardrail_flags=flags,
    )
