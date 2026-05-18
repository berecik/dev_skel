"""DSPy LM factory bound to the project's OllamaConfig.

Every DSPy module in skel_rag eventually goes through here. The
returned LM is memoised on (model, base_url, temperature, timeout)
so the per-target loop reuses one client instead of re-creating
the litellm HTTP session per call.

Phase-specific variants (FIX, CREATE_TEST, CHECK_TEST, DOCS) are
not constructed here — callers build a sibling config via
``cfg.for_fix()`` etc. and pass it back through make_lm().
"""

from __future__ import annotations

from functools import lru_cache

import dspy

from skel_rag.config import OllamaConfig


@lru_cache(maxsize=8)
def _cached(model: str, base_url: str, temperature: float, timeout: int) -> dspy.LM:
    return dspy.LM(
        f"ollama_chat/{model}",
        api_base=base_url,
        api_key="",
        temperature=temperature,
        timeout=timeout,
    )


def make_lm(cfg: OllamaConfig) -> dspy.LM:
    """Return a memoised :class:`dspy.LM` for *cfg*.

    The cache key is ``(model, base_url, temperature, timeout)`` so
    sibling configs produced via ``cfg.for_fix()`` / ``for_create_test()``
    etc. each get their own LM but repeat lookups inside the per-target
    loop reuse the same litellm session.
    """

    return _cached(cfg.model, cfg.base_url, cfg.temperature, cfg.timeout)
