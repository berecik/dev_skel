"""Signature for one per-target file generation in the per-target phase.

The fields here used to be string-templated in every manifest's
SYSTEM_PROMPT. By declaring them once at the framework level, every
manifest collapses to (a) target paths + reference templates and
(b) any per-skeleton overrides expressed as Pydantic
dspy.InputField hints — no more 250-line prompt strings."""

from __future__ import annotations

import dspy


class GenerateFile(dspy.Signature):
    """Rewrite one skeleton reference template for the user's domain.

    You are a senior engineer regenerating ONE file inside a generated
    service. Follow the reference's structure, indentation, and import
    style. Replace the example entity (`ExampleItem` / `example_item` /
    `example_items`) with the user's entity. Output ONLY the file
    contents — no markdown fences, no commentary.
    """

    skeleton_name: str = dspy.InputField(desc="e.g. python-fastapi-skel")
    target_path: str = dspy.InputField(desc="relative path of the file being generated")
    reference_template: str = dspy.InputField(desc="the example_items reference content")
    retrieved_context: str = dspy.InputField(desc="RAG-retrieved sibling files (may be empty)")
    prior_outputs: str = dspy.InputField(desc="files already generated earlier in this run")
    item_class: str = dspy.InputField(desc="PascalCase entity name, e.g. Order")
    item_name: str = dspy.InputField(desc="snake_case entity, e.g. order")
    items_plural: str = dspy.InputField(desc="snake_case plural, e.g. orders")
    service_label: str = dspy.InputField(desc="human service name, e.g. 'Order Service'")
    auth_type: str = dspy.InputField(desc="'jwt' | 'session' | 'none'")
    backend_extra: str = dspy.InputField(desc="user-supplied domain instructions (may be empty)")

    file_contents: str = dspy.OutputField(
        desc="exact contents of the new file, no fences, no preamble"
    )
