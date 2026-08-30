"""LLM client with retries and a model fallback.

The assessment requires demonstrated handling of LLM failures. Two independent
mechanisms cover different failure shapes:

* **Retry with exponential backoff** (tenacity) for transient faults - a 503,
  a dropped connection, a momentary rate limit.
* **Model fallback** (LangChain ``with_fallbacks``) for persistent faults - if
  the primary model is unavailable or its daily quota is spent, the same call
  is replayed against a second model rather than failing the request.

Gemini was chosen because its free tier requires no credit card and allows
roughly 1,500 requests per day, which is comfortably more than a POC and a
recorded demo consume.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=4)
def get_llm(temperature: float | None = None) -> BaseChatModel:
    """Return the chat model, with a fallback model attached.

    Cached per temperature so the client and its connection pool are created
    once per process rather than per request.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    if not settings.google_api_key:
        raise LLMError("GOOGLE_API_KEY is not set")

    temp = settings.llm_temperature if temperature is None else temperature

    primary = ChatGoogleGenerativeAI(
        model=settings.llm_model,
        google_api_key=settings.google_api_key,
        temperature=temp,
    )
    secondary = ChatGoogleGenerativeAI(
        model=settings.llm_fallback_model,
        google_api_key=settings.google_api_key,
        temperature=temp,
    )
    return primary.with_fallbacks([secondary])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def ainvoke(messages: list[BaseMessage], *, temperature: float | None = None) -> str:
    """Call the model and return its text.

    Raises:
        LLMError: after retries and the fallback model are both exhausted.
    """
    try:
        response = await get_llm(temperature).ainvoke(messages)
    except Exception as exc:  # noqa: BLE001 - normalised into a domain error
        log.warning("llm_call_failed", error=str(exc))
        raise LLMError(f"language model call failed: {exc}") from exc
    return str(response.content)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def astructured(messages: list[BaseMessage], schema: type[T]) -> T:
    """Call the model and parse the reply into a Pydantic model.

    Structured output is used for every internal decision (routing, planning,
    validation) so control flow depends on validated fields rather than on
    string-matching free text - which is both safer and far easier to test.
    """
    try:
        chain: Any = get_llm().with_structured_output(schema)
        return await chain.ainvoke(messages)
    except Exception as exc:  # noqa: BLE001
        log.warning("llm_structured_call_failed", schema=schema.__name__, error=str(exc))
        raise LLMError(f"structured model call failed: {exc}") from exc
