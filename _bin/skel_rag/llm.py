"""Ollama chat client wrapper.

Phase-1 of the DSPy migration: every chat call goes through
:func:`make_lm` in :mod:`skel_rag.dspy_lm`, which constructs a
:class:`dspy.LM` bound to ``ollama_chat/<model>``. litellm (the
backend behind ``dspy.LM``) handles the HTTP transport. Retry on
Ollama-specific transient errors (peer closed, connection refused,
incomplete chunked transfer, ...) stays here because litellm does
not match on those error-string patterns.

Two surfaces are exported:

* :func:`verify` — a quick reachability check that mirrors the
  behaviour of the original ``OllamaClient.verify()``. Uses stdlib
  ``urllib`` against ``GET /api/tags`` (no chat call) so it stays
  fast and never blocks on model load.
* :func:`chat` — a one-shot ``system + user → str`` helper with the
  same signature the legacy code used, so every call site in
  :mod:`skel_ai_lib` and :mod:`skel_rag.agent` works unchanged.

``langchain_ollama`` is no longer imported from this module — DSPy
+ litellm is the only chat transport in-tree. The detached
out-of-tree ``./ai`` runtime keeps its own stdlib-only path
(``_bin/dev_skel_refactor_runtime.py``).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

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

    Implemented with stdlib ``urllib`` because we want a fast,
    no-tokens check that does not block on model load — neither
    ``dspy.LM`` nor litellm exposes a "list models" route.
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
#  Chat client (DSPy LM via litellm)
# --------------------------------------------------------------------------- #


_MAX_RETRIES = 3
_RETRY_DELAY_S = 10


def chat(config: OllamaConfig, system: str, user: str) -> str:
    """Send one system+user turn through DSPy -> litellm -> Ollama.

    The signature is preserved so every existing caller in
    :mod:`skel_ai_lib` and :mod:`skel_rag.agent` works unchanged.
    Retries on transient connection errors (peer closed, refused,
    timeout) are kept here because DSPy/litellm do not retry on
    error-string patterns specific to Ollama model reloads or
    GPU-OOM recovery.
    """

    from skel_rag.dspy_lm import make_lm
    import time as _time

    lm = make_lm(config)
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = lm(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
            )
            # litellm returns list[str] when called raw.
            if isinstance(response, list):
                if not response:
                    raise OllamaError("Ollama returned an empty response list")
                return response[0]
            return response
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            err_str = str(exc).lower()
            is_transient = any(
                k in err_str
                for k in (
                    "peer closed",
                    "connection refused",
                    "incomplete chunked",
                    "connection reset",
                    "timed out",
                    "eof occurred",
                )
            )
            if is_transient and attempt < _MAX_RETRIES:
                logger.warning(
                    "Ollama transient error (attempt %d/%d): %s — "
                    "retrying in %ds...",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    _RETRY_DELAY_S,
                )
                _time.sleep(_RETRY_DELAY_S)
                continue
            if isinstance(exc, OllamaError):
                raise
            raise OllamaError(str(exc)) from exc

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
