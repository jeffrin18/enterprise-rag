from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_evaluate, routes_ingest, routes_query
from app.core.config import get_settings

settings = get_settings()

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("enterprise_rag")

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Agentic Enterprise Knowledge Graph & Multi-Source RAG Pipeline — "
        "hybrid Graph-RAG ingestion, LangGraph multi-agent routing with "
        "self-correction, and Pydantic-enforced structured outputs."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_ingest.router)
app.include_router(routes_query.router)
app.include_router(routes_evaluate.router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@app.on_event("startup")
async def on_startup():
    logger.info("Starting %s in %s mode", settings.APP_NAME, settings.ENV)
