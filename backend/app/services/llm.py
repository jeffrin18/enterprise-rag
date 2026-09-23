"""
Thin LLM client wrapper.

Two capabilities are exposed:
  - `complete(prompt, system)`            -> free-text completion
  - `complete_structured(prompt, schema)` -> a validated instance of `schema`

`complete_structured` is how we guarantee "zero JSON structural failures":
we use Anthropic tool-use (a single forced tool whose input_schema IS the
Pydantic model's JSON schema) so the model cannot return malformed JSON —
the API itself enforces the schema, and we additionally validate through
Pydantic before returning. On validation failure we retry once with the
error fed back to the model.
"""
from __future__ import annotations

import json
import logging
from typing import TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T", bound=BaseModel)

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def complete(prompt: str, system: str = "", max_tokens: int = 1024) -> str:
    client = get_client()
    resp = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system or "You are a precise enterprise knowledge assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in resp.content if b.type == "text"]
    return "\n".join(parts).strip()


async def complete_structured(
    prompt: str,
    schema: type[T],
    system: str = "",
    max_tokens: int = 2048,
    max_retries: int = 1,
) -> T:
    """
    Force the model to respond via a single tool call whose schema matches
    `schema`, then validate. Retries once with the validation error appended
    to the prompt if parsing/validation fails.
    """
    client = get_client()
    tool_name = f"emit_{schema.__name__.lower()}"
    tool_def = {
        "name": tool_name,
        "description": f"Emit a structured {schema.__name__} object matching the required schema.",
        "input_schema": schema.model_json_schema(),
    }

    last_error: Exception | None = None
    current_prompt = prompt

    for attempt in range(max_retries + 1):
        resp = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system or "You produce only structured tool calls, no prose.",
            tools=[tool_def],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": current_prompt}],
        )
        tool_block = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_block is None:
            last_error = ValueError("Model did not return a tool_use block")
        else:
            try:
                return schema.model_validate(tool_block.input)
            except ValidationError as e:
                last_error = e
                current_prompt = (
                    f"{prompt}\n\nYour previous structured response failed validation "
                    f"with error:\n{e}\n\nPlease re-emit a fully valid object."
                )
                logger.warning("Structured output validation failed (attempt %s): %s", attempt, e)

    raise RuntimeError(f"complete_structured failed after {max_retries + 1} attempts: {last_error}")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embedding call. Swap this implementation for your provider of choice
    (OpenAI embeddings, Voyage, local sentence-transformers, etc).
    Kept provider-agnostic and isolated so the rest of the pipeline never
    needs to know which embedding backend is active.
    """
    if settings.OPENAI_API_KEY:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client.embeddings.create(model=settings.EMBEDDING_MODEL, input=texts)
        return [d.embedding for d in resp.data]

    # Local fallback: sentence-transformers (no external API key required).
    from sentence_transformers import SentenceTransformer
    global _local_embedder
    try:
        _local_embedder
    except NameError:
        _local_embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _local_embedder.encode(texts, normalize_embeddings=True).tolist()
