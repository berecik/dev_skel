"""Phase-1: dspy_lm.make_lm() returns a configured dspy.LM bound to
the right Ollama endpoint and model for the given OllamaConfig."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from skel_rag.config import OllamaConfig  # noqa: E402

dspy = pytest.importorskip("dspy")
from skel_rag.dspy_lm import make_lm  # noqa: E402


def test_make_lm_uses_config_model_and_base_url():
    cfg = OllamaConfig(
        model="qwen3-coder:30b",
        base_url="http://localhost:11434",
        temperature=0.2,
        timeout=600,
    )
    lm = make_lm(cfg)
    assert isinstance(lm, dspy.LM)
    assert lm.model == "ollama_chat/qwen3-coder:30b"
    assert lm.kwargs["api_base"] == "http://localhost:11434"
    assert lm.kwargs["temperature"] == 0.2


def test_make_lm_caches_by_model_and_url():
    cfg = OllamaConfig(model="m", base_url="http://h:1", temperature=0.2, timeout=60)
    a = make_lm(cfg)
    b = make_lm(cfg)
    assert a is b, "DSPy LM should be memoised so per-target loop reuses one client"
