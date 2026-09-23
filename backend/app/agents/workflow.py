"""
Assembles the full agentic workflow:

    START -> router
               |-- vector_search   --> vector_retrieval   --\
               |-- graph_traversal --> graph_retrieval     --+--> generate_answer -> critique
               |-- structured_sql  --> sql_retrieval       --/                          |
               |-- hybrid          --> hybrid_retrieval    -/                accept -> END
                                                                              retry  -> rewrite_and_retry
                                                                                          |
                                                                                (loops back into the
                                                                                 SAME retrieval node
                                                                                 that was originally routed to)
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.critique_agent import (
    critique_node, critique_router, generate_answer_node, rewrite_and_retry_node,
)
from app.agents.graph_state import AgentState
from app.agents.retrieval_agents import (
    graph_retrieval_node, hybrid_retrieval_node, sql_retrieval_node, vector_retrieval_node,
)
from app.agents.router_agent import route_selector, router_node

RETRIEVAL_NODES = {
    "vector_retrieval": vector_retrieval_node,
    "graph_retrieval": graph_retrieval_node,
    "sql_retrieval": sql_retrieval_node,
    "hybrid_retrieval": hybrid_retrieval_node,
}


def build_workflow():
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    for name, fn in RETRIEVAL_NODES.items():
        graph.add_node(name, fn)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("critique", critique_node)
    graph.add_node("rewrite_and_retry", rewrite_and_retry_node)

    graph.set_entry_point("router")
    graph.add_conditional_edges("router", route_selector, {
        name: name for name in RETRIEVAL_NODES
    })
    for name in RETRIEVAL_NODES:
        graph.add_edge(name, "generate_answer")

    graph.add_edge("generate_answer", "critique")
    graph.add_conditional_edges("critique", critique_router, {
        "finalize": END,
        "rewrite_and_retry": "rewrite_and_retry",
    })

    # Self-correction loop: after rewriting, re-enter the SAME retrieval node
    # the router originally chose (looked up dynamically via state["route"]).
    graph.add_conditional_edges(
        "rewrite_and_retry",
        lambda state: route_selector(state),
        {name: name for name in RETRIEVAL_NODES},
    )

    return graph.compile()


# Compiled once at import time; reused across requests.
compiled_workflow = build_workflow()


async def run_query_workflow(question: str, session_id: str | None, top_k: int) -> AgentState:
    initial_state: AgentState = {
        "question": question,
        "session_id": session_id,
        "top_k": top_k,
        "guardrail_flags": [],
        "self_corrections": 0,
        "agent_steps": [],
    }
    final_state = await compiled_workflow.ainvoke(initial_state)
    return final_state
