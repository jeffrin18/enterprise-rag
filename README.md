# Agentic Enterprise Knowledge Graph & Multi-Source RAG Pipeline

Solves context loss in complex document QA by combining a **Neo4j knowledge
graph**, a **Qdrant vector store**, and a **LangGraph multi-agent router with
a self-correction loop**, all behind Pydantic-enforced structured outputs.

## Architecture

```
                              ┌─────────────────────────────┐
                              │        Next.js Frontend      │
                              │  Chat · Agent Trace · Graph  │
                              └──────────────┬───────────────┘
                                             │ /api/*
                              ┌──────────────▼───────────────┐
                              │          FastAPI              │
                              │  /ingest  /query  /evaluate   │
                              └──────────────┬───────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                LangGraph Workflow                │
                    │                                                   │
                    │   router ──┬─▶ vector_retrieval ───┐              │
                    │             ├─▶ graph_retrieval ────┤              │
                    │             ├─▶ sql_retrieval ───────┼─▶ generate  │
                    │             └─▶ hybrid_retrieval ───┘    _answer  │
                    │                                            │      │
                    │                                       critique     │
                    │                                       (Ragas-style)│
                    │                                      accept │ retry│
                    │                                        END  ▼      │
                    │                                  rewrite_and_retry │
                    │                                  (loops back up   │
                    │                                   to same route)   │
                    └───────────────────────────────────────────────────┘
                              │                          │
                    ┌─────────▼─────────┐      ┌─────────▼─────────┐
                    │   Qdrant (vector)  │      │  Neo4j (graph)     │
                    └────────────────────┘      └────────────────────┘
```

### 1. Hybrid Context Pipeline (Ingestion)
`app/services/ingestion.py`
- Parses PDF/text, sentence-aware semantic chunking with overlap.
- Every chunk passes through **input guardrails** (PII masking + prompt-injection
  scan) before it is embedded or sent to an LLM.
- Chunks are embedded and upserted into **Qdrant**.
- The same chunks are run through an LLM extraction call (forced structured
  output via `GraphExtractionResult`) and the resulting entities/relationships
  are written into **Neo4j**, linked back to their source `Chunk` node for
  provenance.

### 2. Multi-Agent Routing & Self-Correction (LangGraph)
`app/agents/`
- **Router Agent** (`router_agent.py`): classifies the query into
  `vector_search`, `graph_traversal`, `structured_sql`, or `hybrid`, and for
  the graph/SQL routes also emits the read-only query itself.
- **Retrieval Agents** (`retrieval_agents.py`): one node per route. The graph
  node rejects any Cypher containing write/admin clauses (`CREATE`, `MERGE`,
  `DELETE`, `SET`, `DROP`, `CALL apoc.create`, …) before executing it — the
  primary Cypher-injection guardrail.
- **Critique Agent** (`critique_agent.py`): scores `faithfulness` and
  `context_recall` (Ragas-style, LLM-as-judge grounded strictly in retrieved
  context) as a validated `CritiqueVerdict`. If either score is below
  threshold or a hallucination is flagged, it returns `verdict="retry"`.
- **Self-correction loop**: on `retry`, `rewrite_and_retry_node` rewrites the
  search query from the critique feedback and the graph loops back into the
  **same** retrieval node the router originally selected. Bounded by
  `MAX_SELF_CORRECTION_LOOPS` so the graph always terminates.

### 3. Guardrails & Structured Output
- Every LLM call that needs to return data (router decision, graph
  extraction, critique verdict) goes through `services/llm.py ::
  complete_structured()`, which forces a single Anthropic tool call whose
  `input_schema` **is** the Pydantic model's JSON schema, then validates with
  Pydantic — retrying once with the validation error fed back on failure.
  This is what guarantees zero JSON structural failures.
- `core/security.py` implements deterministic (non-LLM, cheap, on every
  request) **PII masking** (emails, phone numbers, card numbers, SSN/Aadhaar-
  like ids, IPs) and **prompt-injection detection** (instruction-override,
  role-hijack, prompt-exfiltration, tool-hijack, delimiter-escape patterns),
  applied to both user queries and ingested document chunks (indirect
  injection defense).

### 4. UI & Explainability
- `components/AgentStepsTimeline.tsx`: renders the `agent_steps` trail
  returned in every `/query` response — Routing Query → Executing
  Vector/Cypher/SQL → Generating Answer → Self-Evaluating Response → (retry
  loop if triggered) → Final Output.
- `components/GraphVisualizer.tsx`: radial SVG layout of the `subgraph`
  (nodes/edges) returned for graph-routed queries, color-coded by entity
  type, hover-highlighted edges.
- `components/ChatInterface.tsx`: chat UI showing the answer, route taken,
  faithfulness/recall scores, self-correction count, guardrail flags, and
  expandable retrieved context chunks.

## Project Layout

```
enterprise-rag/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + CORS + routers
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings, env-driven
│   │   │   └── security.py         # PII masking + prompt-injection guardrails
│   │   ├── schemas/
│   │   │   └── models.py           # all Pydantic contracts (API + structured LLM output)
│   │   ├── services/
│   │   │   ├── llm.py              # Anthropic client, complete_structured()
│   │   │   ├── vector_store.py     # Qdrant (+ Pinecone stub) wrapper
│   │   │   ├── graph_store.py      # Neo4j wrapper, Cypher-injection guard
│   │   │   └── ingestion.py        # chunk → embed → extract → persist
│   │   ├── agents/
│   │   │   ├── graph_state.py      # LangGraph shared state (TypedDict)
│   │   │   ├── router_agent.py     # intent classification + routing
│   │   │   ├── retrieval_agents.py # vector / graph / sql / hybrid nodes
│   │   │   ├── critique_agent.py   # generation + self-correction loop
│   │   │   └── workflow.py         # StateGraph assembly
│   │   └── api/
│   │       ├── routes_ingest.py    # POST /ingest
│   │       ├── routes_query.py     # POST /query
│   │       └── routes_evaluate.py  # POST /evaluate (Ragas)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                        # Next.js App Router (page.tsx, layout.tsx)
│   ├── components/                 # ChatInterface, AgentStepsTimeline, GraphVisualizer
│   ├── lib/                        # api.ts (fetch client), types.ts (mirrors backend schemas)
│   ├── package.json / tailwind.config.ts / next.config.js
│   └── Dockerfile
├── docker-compose.yml               # neo4j + qdrant + backend + frontend
├── .env.example
└── README.md
```

## Running it

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY (and optionally OPENAI_API_KEY for embeddings) in .env

docker compose up --build
```

- Frontend: http://localhost:3000
- Backend docs (Swagger): http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (user `neo4j`, password from `.env`)
- Qdrant dashboard: http://localhost:6333/dashboard

### Ingest a document

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"source_path": "/app/data/handbook.pdf", "metadata": {"department": "HR"}}'
```

### Ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How is the Payments team connected to the Compliance policy?"}'
```

### Evaluate an answer with Ragas

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the refund window?",
    "answer": "The refund window is 30 days from purchase.",
    "contexts": ["Customers may request a refund within 30 days of purchase."]
  }'
```

## Local development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

You'll still need Neo4j and Qdrant reachable (run just those two services via
`docker compose up neo4j qdrant`, or point `NEO4J_URI` / `QDRANT_URL` at
managed instances).

## Notes on production hardening

- Swap `complete_structured`'s retry-on-validation-failure with a circuit
  breaker + dead-letter queue for ingestion at scale.
- Add an auth layer (API key or OAuth) in front of `/ingest` and `/query` —
  none is included here since it's environment-specific.
- The SQL route assumes a `metrics` table exists; point `SQL_DATABASE_URL` at
  your real structured warehouse and adjust the router's system prompt.
- Ragas evaluation in `/evaluate` makes its own LLM calls; consider caching
  or batching for a nightly regression suite rather than synchronous calls.
