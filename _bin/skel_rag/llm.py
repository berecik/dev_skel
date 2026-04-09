"""Ollama chat client wrapper.

We previously talked to Ollama via stdlib ``urllib.request`` (see the
old ``OllamaClient`` in ``skel_ai_lib.py``). The RAG agent now uses
``langchain_ollama.ChatOllama`` so the chat call goes through the same
abstraction LangChain uses for retrieval, callbacks, and streaming.

Two compatibility shims live here:

* :func:`verify` — a quick reachability check that mirrors the
  behaviour of the original ``OllamaClient.verify()`` (uses ``GET
  /api/tags`` because LangChain has no built-in equivalent).
* :func:`chat` — a one-shot ``system + user → str`` helper with the
  same signature as the legacy method, so call sites in the shim do
  not need to change.

LangChain itself is imported lazily so this module can be imported in
contexts where ``langchain-ollama`` is not yet installed.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

from skel_rag.config import OllamaConfig

logger = logging.getLogger("skel_rag.llm")


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable or returns an error response."""


# --------------------------------------------------------------------------- #
#  Reachability check
# --------------------------------------------------------------------------- #


def verify(config: OllamaConfig) -> None:
    """Confirm Ollama is reachable and the requested model is loaded.

    Raises :class:`OllamaError` with a friendly message on any failure
    so the CLI can surface a single actionable error.

    Implemented with stdlib ``urllib`` because LangChain's chat client
    does not expose a "list models" route — and we want a fast,
    no-tokens check that does not block on model load.
    """

    url = f"{config.base_url}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise OllamaError(
            f"Could not reach Ollama at {config.base_url}: {exc}.\n"
            "Make sure `ollama serve` is running, or set OLLAMA_BASE_URL."
        ) from exc

    names = [m.get("name", "") for m in payload.get("models", [])]
    if config.model not in names:
        available = ", ".join(sorted(n for n in names if n)) or "(none)"
        raise OllamaError(
            f"Ollama model '{config.model}' is not available locally.\n"
            f"Models present: {available}\n"
            f"Pull it with: ollama pull {config.model}"
        )


# --------------------------------------------------------------------------- #
#  Chat client
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=4)
def _make_chat_model(model: str, base_url: str, temperature: float, timeout: int) -> Any:
    try:
        from langchain_ollama import ChatOllama  # type: ignore
    except ImportError as exc:
        raise OllamaError(
            "langchain-ollama is not installed. Run "
            "`make install-rag-deps` to enable the RAG agent."
        ) from exc

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
        # langchain-ollama uses ``request_timeout`` (seconds, float).
        request_timeout=float(timeout),
    )


def make_chat_model(config: OllamaConfig) -> Any:
    """Return a (cached) ``ChatOllama`` instance for *config*."""

    return _make_chat_model(
        config.model, config.base_url, config.temperature, config.timeout
    )


def chat(config: OllamaConfig, system: str, user: str) -> str:
    """Send one ``system + user`` turn and return the assistant text.

    The signature mirrors the legacy ``OllamaClient.chat`` so call
    sites in the shim do not need to change. Errors are wrapped in
    :class:`OllamaError` so the test-and-fix loop can recover the
    same way it did before.
    """

    try:
        from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
    except ImportError as exc:
        raise OllamaError(
            "langchain-core is not installed. Run "
            "`make install-rag-deps` to enable the RAG agent."
        ) from exc

    model = make_chat_model(config)
    try:
        response = model.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
    except Exception as exc:  # noqa: BLE001 — surface a single friendly error
        raise OllamaError(
            f"Ollama request failed: {exc}. Is `ollama serve` running?"
        ) from exc

    content = getattr(response, "content", None)
    if isinstance(content, list):
        # Some langchain providers wrap multimodal output in a list of
        # ``{"type": "text", "text": "..."}`` dicts. Concatenate text
        # blocks so the rest of the pipeline keeps treating chat output
        # as a single string.
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                text_parts.append(block)
        return "".join(text_parts)
    if isinstance(content, str):
        return content
    raise OllamaError(f"Unexpected ChatOllama response: {response!r}")
