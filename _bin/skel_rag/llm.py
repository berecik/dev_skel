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
            "Make sure `ollama serve` is running, or set OLLAMA_HOST."
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
#  Stdlib fallback (no langchain required)
# --------------------------------------------------------------------------- #

_HAS_LANGCHAIN = True
try:
    from langchain_ollama import ChatOllama  # type: ignore
    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
except ImportError:
    _HAS_LANGCHAIN = False

if not _HAS_LANGCHAIN:
    logger.info(
        "langchain-ollama not installed — using stdlib Ollama client. "
        "Run `make install-rag-deps` for the full RAG pipeline."
    )


def _chat_stdlib(config: OllamaConfig, system: str, user: str) -> str:
    """Direct HTTP via Ollama's OpenAI-compatible endpoint.

    This is the primary chat path (not a fallback). LangChain's
    ChatOllama uses httpx which deadlocks on large responses from
    remote Ollama servers. The stdlib ``urllib.request`` path is
    simpler and fully reliable.

    Supports optional ``OLLAMA_NUM_CTX`` and ``OLLAMA_NUM_PREDICT``
    env vars to control context window and output cap. Sends
    ``keep_alive: "24h"`` to prevent model unloading between calls.
    """
    import os as _os

    url = f"{config.base_url}/v1/chat/completions"
    body: dict = {
        "model": config.model,
        "temperature": config.temperature,
        "stream": False,
        "keep_alive": "24h",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    # Optional context window and output cap via env vars.
    _num_ctx = _os.environ.get("OLLAMA_NUM_CTX", "").strip()
    if _num_ctx:
        body["num_ctx"] = int(_num_ctx)
    _num_predict = _os.environ.get("OLLAMA_NUM_PREDICT", "").strip()
    if _num_predict:
        body["num_predict"] = int(_num_predict)

    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=config.timeout
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OllamaError(
            f"Ollama returned HTTP {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise OllamaError(
            f"Ollama request failed: {exc}. Is `ollama serve` running?"
        ) from exc

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OllamaError(f"Unexpected Ollama response: {payload!r}") from exc


# --------------------------------------------------------------------------- #
#  Chat client
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=4)
def _make_chat_model(model: str, base_url: str, temperature: float, timeout: int) -> Any:
    if not _HAS_LANGCHAIN:
        return None

    import os as _os

    kwargs: dict = {
        "model": model,
        "base_url": base_url,
        "temperature": temperature,
        "request_timeout": float(timeout),
    }
    # Optional: set explicit context window and output cap via env vars.
    # Leave unset by default so Ollama uses the model's native defaults.
    _num_ctx = _os.environ.get("OLLAMA_NUM_CTX", "").strip()
    if _num_ctx:
        kwargs["num_ctx"] = int(_num_ctx)
    _num_predict = _os.environ.get("OLLAMA_NUM_PREDICT", "").strip()
    if _num_predict:
        kwargs["num_predict"] = int(_num_predict)

    return ChatOllama(**kwargs)


def make_chat_model(config: OllamaConfig) -> Any:
    """Return a (cached) ``ChatOllama`` instance for *config*.

    Returns ``None`` when langchain is not installed.
    """

    return _make_chat_model(
        config.model, config.base_url, config.temperature, config.timeout
    )


_MAX_RETRIES = 3
_RETRY_DELAY_S = 10


def chat(config: OllamaConfig, system: str, user: str) -> str:
    """Send one ``system + user`` turn and return the assistant text.

    The signature mirrors the legacy ``OllamaClient.chat`` so call
    sites in the shim do not need to change. Errors are wrapped in
    :class:`OllamaError` so the test-and-fix loop can recover the
    same way it did before.

    Falls back to a direct HTTP call via Ollama's OpenAI-compatible
    endpoint when ``langchain-ollama`` / ``langchain-core`` are not
    installed.

    Retries up to ``_MAX_RETRIES`` times on transient connection
    errors (peer closed, connection refused, timeout) with a short
    delay between attempts. This handles Ollama model reloads and
    transient OOM-recovery on GPU-constrained hosts.
    """

    # Always use the stdlib HTTP path — it's more reliable than
    # LangChain's ChatOllama which can hang on large responses due to
    # httpx/streaming issues. The stdlib path uses urllib.request with
    # explicit timeouts and retry logic.
    import time as _time

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return _chat_stdlib(config, system, user)
        except OllamaError as exc:
            last_exc = exc
            err_str = str(exc).lower()
            is_transient = any(k in err_str for k in (
                "peer closed", "connection refused", "incomplete chunked",
                "connection reset", "timed out", "eof occurred",
            ))
            if is_transient and attempt < _MAX_RETRIES:
                logger.warning(
                    "Ollama transient error (attempt %d/%d): %s — "
                    "retrying in %ds...",
                    attempt, _MAX_RETRIES, exc, _RETRY_DELAY_S,
                )
                _time.sleep(_RETRY_DELAY_S)
                continue
            raise

    raise OllamaError(
        f"Ollama request failed after {_MAX_RETRIES} retries: {last_exc}"
    )


# --------------------------------------------------------------------------- #
#  Instrumented chat (observability layer)
# --------------------------------------------------------------------------- #


def chat_with_metrics(
    config: OllamaConfig, system: str, user: str, *, verbose: int = 0
) -> tuple[str, "LlmCallMetrics"]:
    """``chat()`` with timing and token estimation.

    Returns ``(response_text, metrics)``. Import is lazy so callers
    that only use plain ``chat()`` never pull in the metrics module.
    """

    import sys
    import time

    from skel_rag.metrics import LlmCallMetrics

    input_chars = len(system) + len(user)

    if verbose >= 2:
        input_tokens_est = input_chars // 4
        print(
            f"    [rag] prompt: system={len(system):,} chars, "
            f"user={len(user):,} chars (~{input_tokens_est:,} tokens)",
            file=sys.stderr,
        )

    t0 = time.monotonic()
    response = chat(config, system=system, user=user)
    elapsed = time.monotonic() - t0

    output_chars = len(response)
    metrics = LlmCallMetrics(
        elapsed_s=elapsed,
        input_chars=input_chars,
        output_chars=output_chars,
    )

    if verbose >= 1:
        print(
            f"    [rag] Ollama: {elapsed:.1f}s, "
            f"response={output_chars:,} chars "
            f"(~{metrics.output_tokens_est} tokens)",
            file=sys.stderr,
        )
    if verbose >= 2:
        print(
            f"    [rag] throughput: {metrics.throughput_tok_s:.1f} tok/s",
            file=sys.stderr,
        )

    return response, metrics
