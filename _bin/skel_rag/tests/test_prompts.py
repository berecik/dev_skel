"""Tests for ``skel_rag.prompts``."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from skel_rag.prompts import (  # noqa: E402
    build_query_for_target,
    render_retrieved_block,
)
from skel_rag.retriever import RetrievedChunk  # noqa: E402


def _chunk(
    *,
    rel_path: str = "app/example_items/models.py",
    name: str = "ExampleItemBase",
    kind: str = "class",
    language: str = "python",
    start_line: int = 10,
    end_line: int = 25,
    body: str = "class ExampleItemBase(BaseModel):\n    title: str\n",
) -> RetrievedChunk:
    return RetrievedChunk(
        rel_path=rel_path,
        file=f"/skel/{rel_path}",
        language=language,
        kind=kind,
        name=name,
        start_line=start_line,
        end_line=end_line,
        source=body,
    )


class RenderRetrievedBlockTests(unittest.TestCase):
    def test_empty_returns_placeholder(self) -> None:
        text = render_retrieved_block([], max_chars=10000)
        self.assertIn("no relevant context", text)

    def test_single_chunk_renders_with_header_and_fence(self) -> None:
        text = render_retrieved_block([_chunk()], max_chars=10000)
        self.assertIn("### app/example_items/models.py:10-25 · class · ExampleItemBase", text)
        self.assertIn("```python", text)
        self.assertIn("class ExampleItemBase", text)

    def test_truncates_to_max_chars(self) -> None:
        big_body = "x" * 5000
        chunks = [_chunk(name=f"a{i}", body=big_body) for i in range(10)]
        text = render_retrieved_block(chunks, max_chars=8000)
        # Should keep the first chunk plus the truncation marker, not all 10.
        self.assertIn("further results truncated", text)
        self.assertLess(len(text), 25000)


class BuildQueryTests(unittest.TestCase):
    def test_query_includes_path_entity_and_auth(self) -> None:
        query = build_query_for_target(
            target_path="app/ticket_api/routes.py",
            target_description="FastAPI endpoints",
            target_prompt="Rewrite app/example_items/routes.py for the {item_class} entity.",
            item_class="Ticket",
            item_name="ticket",
            items_plural="tickets",
            service_label="Ticket API",
            auth_type="jwt",
        )
        self.assertIn("app/ticket_api/routes.py", query)
        self.assertIn("FastAPI endpoints", query)
        self.assertIn("Ticket", query)
        self.assertIn("Ticket API", query)
        self.assertIn("jwt", query)

    def test_query_truncates_long_prompt_prefix(self) -> None:
        long_prompt = "very long instruction " * 200
        query = build_query_for_target(
            target_path="x.py",
            target_description="",
            target_prompt=long_prompt,
            item_class="X",
            item_name="x",
            items_plural="xs",
            service_label="X",
            auth_type="none",
        )
        # Total query is bounded; the prompt prefix slice is the dominant
        # component but cannot exceed our 600-char cap.
        self.assertLess(len(query), 1500)


if __name__ == "__main__":
    unittest.main()
