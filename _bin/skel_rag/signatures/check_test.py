"""Signature for the CHECK_TEST reviewer step.

Mirrors the legacy ``RagAgent._maybe_check_target`` reviewer in a
declarative DSPy form: feed it the just-generated file together with
any sibling files already produced in this run plus the wrapper-shared
OpenAPI contract, get back an ``OK`` / ``FAIL`` verdict and a one-line
reason. The :class:`CheckedGenerateProgram` (see
``skel_rag.programs.generate_with_check``) uses this signature as the
review step composed after the per-target generator.
"""

from __future__ import annotations

from typing import Literal

import dspy


class ReviewGeneratedFile(dspy.Signature):
    """Spot REAL issues — references to symbols that no sibling file
    defines, imports that won't resolve, methods called on a class
    that doesn't declare them, assertions that contradict the
    contract. Do NOT nitpick style.
    """

    generated_file: str = dspy.InputField(
        desc="the just-generated file contents under review"
    )
    sibling_files: str = dspy.InputField(
        desc="files already generated earlier in this run (may be empty)"
    )
    contract: str = dspy.InputField(
        desc="OpenAPI snippet, may be empty"
    )

    verdict: Literal["OK", "FAIL"] = dspy.OutputField(
        desc="OK if the file is consistent; FAIL otherwise"
    )
    reason: str = dspy.OutputField(
        desc="one-line explanation if FAIL, else empty"
    )
