"""
Generation node + Critique Agent (self-correction loop).

Flow:
  generate_answer -> critique_answer -> [accept: END | retry: rewrite params -> back to router's
                                          chosen retrieval node]

The critique agent scores faithfulness/context-recall using the same
technique Ragas uses conceptually (LLM-as-judge grounded strictly in the
retrieved context), returned as a validated Pydantic object so the
self-correction decision is deterministic code, not prose-parsing.
"""
from __future__ import annotations

from app.agents.graph_state import AgentState, log_step
from app.core.config import get_settings
from app.schemas.models import CritiqueVerdict
from app.services.llm import complete, complete_structured

settings = get_settings()

GENERATION_SYSTEM_PROMPT = """You are an enterprise knowledge assistant. Answer the user's
question using ONLY the provided context. If the context is insufficient, say so explicitly
rather than guessing. Cite which pieces of context you used implicitly through your phrasing,
but do not fabricate any fact absent from the context."""

CRITIQUE_SYSTEM_PROMPT = """You are a Critique Agent performing automated evaluation of a
RAG answer, similar to Ragas faithfulness/context-recall scoring. Given the question, the
retrieved context, and the generated answer:

1. faithfulness_score (0-1): does every claim in the answer trace back to the context?
2. context_recall_score (0-1): does the context contain enough information to fully answer
   the question?
3. hallucination_detected: true if the answer states anything not supported by context.
4. missing_information: bullet list of what's missing from context if recall is low.
5. verdict: "retry" if faithfulness < threshold OR context_recall < threshold OR
   hallucination_detected is true; otherwise "accept".
6. If verdict == retry, give concise retry_instructions describing how the next retrieval
   pass should differ (e.g. broaden the query, target a different entity, use graph instead
   of vector search)."""


def _format_context(chunks) -> str:
    return "\n\n".join(f"[{c.chunk_id}] ({c.source}): {c.text}" for c in chunks) or "(no context retrieved)"


async def generate_answer_node(state: AgentState) -> dict:
    context = _format_context(state.get("retrieved_chunks", []))
    prompt = f"Question: {state['question']}\n\nContext:\n{context}\n\nAnswer the question."
    answer = await complete(prompt, system=GENERATION_SYSTEM_PROMPT, max_tokens=800)
    return {
        "answer": answer,
        **log_step("generate_answer", "Generating Answer", "success",
                    f"Answer drafted from {len(state.get('retrieved_chunks', []))} context chunks"),
    }


async def critique_node(state: AgentState) -> dict:
    context = _format_context(state.get("retrieved_chunks", []))
    prompt = (
        f"Question: {state['question']}\n\nContext:\n{context}\n\n"
        f"Generated answer:\n{state['answer']}\n\n"
        f"faithfulness_threshold={settings.FAITHFULNESS_THRESHOLD}, "
        f"context_recall_threshold={settings.CONTEXT_RECALL_THRESHOLD}"
    )
    critique: CritiqueVerdict = await complete_structured(
        prompt=prompt, schema=CritiqueVerdict, system=CRITIQUE_SYSTEM_PROMPT,
    )

    loops_so_far = state.get("self_corrections", 0)
    # Force-accept once we've hit the max retry budget, regardless of verdict,
    # to guarantee the graph always terminates.
    if loops_so_far >= settings.MAX_SELF_CORRECTION_LOOPS and critique.verdict == "retry":
        critique.verdict = "accept"
        critique.retry_instructions = None

    status = "warning" if critique.verdict == "retry" else "success"
    return {
        "critique": critique,
        **log_step("self_evaluate", "Self-Evaluating Response", status,
                    f"faithfulness={critique.faithfulness_score:.2f} "
                    f"recall={critique.context_recall_score:.2f} verdict={critique.verdict}"),
    }


def critique_router(state: AgentState) -> str:
    """Conditional edge: accept -> END, retry -> rewrite_retrieval."""
    critique = state.get("critique")
    if critique and critique.verdict == "retry":
        return "rewrite_and_retry"
    return "finalize"


async def rewrite_and_retry_node(state: AgentState) -> dict:
    critique = state["critique"]
    new_query = await complete(
        f"Original question: {state['question']}\n"
        f"Critique feedback: {critique.retry_instructions}\n"
        f"Rewrite the search query to address this feedback. Return ONLY the rewritten query.",
        system="You rewrite retrieval queries to improve recall based on critique feedback.",
        max_tokens=150,
    )
    return {
        "rewritten_query": new_query.strip(),
        "self_corrections": state.get("self_corrections", 0) + 1,
        **log_step("self_correct", "Rewriting Search Parameters", "warning",
                    f"Retry #{state.get('self_corrections', 0) + 1}: {new_query.strip()[:120]}"),
    }
