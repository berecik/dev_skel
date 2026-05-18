"""Phase-2: generate_targets_with_dspy() drives one DSPy Predict per
manifest target, runs clean_response, and writes the file. The unit
test mocks out the LM (via RagAgent.chat-equivalent surface) and the
retriever so it runs without Ollama or a real FAISS index.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

dspy = pytest.importorskip("dspy")

from skel_ai_lib import AiManifest, AiTarget, GenerationContext  # noqa: E402
from skel_rag.agent import RagAgent  # noqa: E402
from skel_rag.config import OllamaConfig  # noqa: E402


_MOCK_FILE_CONTENTS = "print('hi')\n"


def _make_ctx(project_dir: Path) -> GenerationContext:
    skeleton_path = project_dir.parent / "skeleton"
    skeleton_path.mkdir(parents=True, exist_ok=True)
    return GenerationContext(
        skeleton_name="python-fastapi-skel",
        skeleton_path=skeleton_path,
        project_root=project_dir.parent,
        project_name="myproj",
        service_subdir=project_dir.name,
        service_label="Order Service",
        item_name="order",
        auth_type="jwt",
        backend_extra="",
    )


def test_generate_targets_with_dspy_writes_mocked_contents(tmp_path: Path) -> None:
    project_dir = tmp_path / "order_service"
    project_dir.mkdir()
    ctx = _make_ctx(project_dir)

    manifest = AiManifest(
        skeleton_name="python-fastapi-skel",
        targets=[
            AiTarget(
                path="dummy.py",
                template=None,
                prompt="prompt",
                language="python",
                description="dummy",
            )
        ],
    )

    cfg = OllamaConfig(
        model="qwen2.5-coder:32b",
        base_url="http://paul:11434",
        temperature=0.2,
        timeout=600,
    )
    agent = RagAgent(ollama_cfg=cfg)

    # Mock retrieval surfaces so the agent treats retrieval as disabled.
    # The agent's get_retriever() already handles None by returning the
    # legacy placeholder block, so we just stub the underlying corpus +
    # retriever to short-circuit before any FAISS calls.
    with patch("skel_rag.agent.corpus_for_skeleton", return_value=None), \
         patch.object(RagAgent, "get_retriever", return_value=None), \
         patch("dspy.Predict") as mock_predict_cls:
        mock_predict_cls.return_value = lambda **kwargs: SimpleNamespace(
            file_contents=_MOCK_FILE_CONTENTS,
        )

        results = agent.generate_targets_with_dspy(
            manifest=manifest,
            ctx=ctx,
            dry_run=False,
            progress=None,
        )

    assert len(results) == 1
    written = project_dir / "dummy.py"
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == _MOCK_FILE_CONTENTS
    assert results[0].written_to == written
    assert results[0].bytes_written == len(_MOCK_FILE_CONTENTS.encode("utf-8"))
