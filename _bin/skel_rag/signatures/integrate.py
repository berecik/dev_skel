"""Signature for the integration phase: wire a new service into its
siblings in the wrapper.

The legacy ``run_integration_phase`` packed every sibling file into a
single ``{wrapper_snapshot}`` blob. The DSPy path keeps the same idea
but pipes the retrieved sibling chunks through a typed
``retrieved_siblings`` field so the optimizer can experiment with the
prompt shape without us hand-editing 17 manifests.
"""

from __future__ import annotations

import dspy


class IntegrateService(dspy.Signature):
    """Write integration code that wires a new service into its sibling
    services in the wrapper. Use the retrieved sibling files as the
    source of truth — never invent route paths or env-var names.
    """

    target_path: str = dspy.InputField(
        desc="relative path of the integration file being generated"
    )
    retrieved_siblings: str = dspy.InputField(
        desc="RAG-retrieved sibling files from the wrapper (may be empty)"
    )
    item_class: str = dspy.InputField(
        desc="PascalCase entity name, e.g. Order"
    )
    service_label: str = dspy.InputField(
        desc="human service name, e.g. 'Order Service'"
    )
    integration_extra: str = dspy.InputField(
        desc="user-supplied integration instructions, may be empty"
    )

    file_contents: str = dspy.OutputField(
        desc="exact contents of the integration file, no fences, no preamble"
    )
