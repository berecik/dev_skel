"""Composed DSPy program: generate one file, then review it.

Wraps :class:`~skel_rag.signatures.generate_file.GenerateFile` with a
post-hoc :class:`~skel_rag.signatures.check_test.ReviewGeneratedFile`
critique step. The legacy :meth:`RagAgent._maybe_check_target` does
the same thing imperatively (parse ``OK`` / ``FAIL: reason`` from a
free-form string and regenerate once on FAIL). This module is the
DSPy-native equivalent.

Retry strategy:

* ``dspy.Suggest`` would be the canonical way to express "if the
  reviewer flags an issue, backtrack and re-run the generator with the
  critique appended". Unfortunately the dspy version pinned in this
  repo (3.2.x at the time of writing) no longer exposes
  ``dspy.Suggest`` / ``dspy.Assert`` / ``dspy.assert_transform_module``
  — the assertions module was removed in the 3.x rewrite. To keep
  parity with the legacy ``_maybe_check_target`` "regenerate once on
  FAIL" semantics, we implement a small manual one-shot retry inside
  :meth:`forward`: on ``verdict == "FAIL"`` we call the generator a
  second time with the reviewer's critique appended to the
  ``backend_extra`` input and return the new prediction.

If a future DSPy release re-adds ``dspy.Suggest`` we can swap the
manual retry for a proper backtracking constraint without changing the
calling code.
"""

from __future__ import annotations

import dspy

from skel_rag.signatures.check_test import ReviewGeneratedFile
from skel_rag.signatures.generate_file import GenerateFile


class CheckedGenerateProgram(dspy.Module):
    """One DSPy call per target, with a reviewer step.

    Pattern:

    1. Call :class:`GenerateFile` predictor to produce ``file_contents``.
    2. Call :class:`ReviewGeneratedFile` predictor with the file, sibling
       files, and OpenAPI contract.
    3. If verdict is ``OK`` → return the original prediction.
    4. If verdict is ``FAIL`` → call the generator a second time with
       the reviewer's reason appended to ``backend_extra`` and return
       the second prediction. The caller still gets a normal DSPy
       ``Prediction`` object so the downstream clean / write path
       doesn't change.
    """

    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.Predict(GenerateFile)
        self.review = dspy.Predict(ReviewGeneratedFile)

    def forward(
        self,
        *,
        sibling_files: str = "",
        contract: str = "",
        **gen_inputs,
    ):
        pred = self.generate(**gen_inputs)
        review = self.review(
            generated_file=getattr(pred, "file_contents", "") or "",
            sibling_files=sibling_files,
            contract=contract,
        )
        verdict = str(getattr(review, "verdict", "OK")).strip().upper()
        if verdict == "OK":
            return pred

        reason = str(getattr(review, "reason", "")).strip()
        # One-shot manual retry: thread the reviewer's reason into
        # ``backend_extra`` so the model sees the critique. We avoid
        # mutating the original kwargs dict to keep the call site
        # deterministic.
        retry_inputs = dict(gen_inputs)
        original_extra = retry_inputs.get("backend_extra", "") or ""
        retry_inputs["backend_extra"] = (
            f"{original_extra}\n\nA reviewer flagged the previous "
            f"version: {reason}\nFix that specific issue in the new "
            "version. Output ONLY the corrected file contents."
        ).strip()
        return self.generate(**retry_inputs)
