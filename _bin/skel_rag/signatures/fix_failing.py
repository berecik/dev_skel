"""Signature for the test/fix loop's per-file repair step.

Mirrors the legacy ``_ask_ollama_to_fix`` / ``_fix_failing_files``
prompts in :mod:`skel_ai_lib`: feed in one source file's current
contents, the failing test output, and any sibling files needed for
context; get back the replacement contents. Composed inside
:class:`skel_rag.programs.test_fix_loop.TestFixLoop` which iterates
the run-tests / patch / re-run cycle.
"""

from __future__ import annotations

import dspy


class FixFailingFile(dspy.Signature):
    """Patch ONE file so the failing test passes. Output ONLY the
    full replacement file contents — no markdown fences, no
    preamble."""

    file_path: str = dspy.InputField(
        desc="relative path of the file being patched"
    )
    current_contents: str = dspy.InputField(
        desc="the file's current contents"
    )
    test_output: str = dspy.InputField(
        desc="stderr+stdout of the failing test, may be truncated"
    )
    sibling_context: str = dspy.InputField(
        desc="other files the failing one depends on"
    )

    fixed_contents: str = dspy.OutputField(
        desc="the full replacement file contents, no fences, no preamble"
    )
