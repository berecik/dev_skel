"""Composed DSPy module for the integration phase.

Mirrors the external behaviour of
:meth:`skel_rag.agent.RagAgent.run_integration_phase` without changing
file-write semantics — the driver
(:meth:`skel_rag.agent.RagAgent.run_integration_phase_with_dspy`) still
owns the per-target loop, retrieval, dry-run skip, and on-disk write.
This module is the single LM call per target: in/out is just the
:class:`IntegrateService` signature wrapped in a ``ChainOfThought``
so the optimizer (Phase 7) has a reasoning trace to tune.
"""

from __future__ import annotations

import dspy

from skel_rag.signatures.integrate import IntegrateService


class IntegrationProgram(dspy.Module):
    """One DSPy call per integration target.

    Constructed once per integration phase; reused inside the per-target
    loop because the LM is configured externally via ``dspy.context``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.integrate = dspy.ChainOfThought(IntegrateService)

    def forward(
        self,
        target_path: str,
        retrieved_siblings: str,
        item_class: str,
        service_label: str,
        integration_extra: str = "",
    ):
        return self.integrate(
            target_path=target_path,
            retrieved_siblings=retrieved_siblings,
            item_class=item_class,
            service_label=service_label,
            integration_extra=integration_extra,
        )
