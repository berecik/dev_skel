"""Prompt assembly helpers for the RAG agent.

The RAG layer adds two new placeholders that manifests can opt into:

* ``{retrieved_context}`` — Markdown rendering of the chunks retrieved
  from the **skeleton corpus** for the current per-target generation.
  Replaces the legacy ``{template}`` placeholder (which keeps working
  for the unmigrated manifests during the transition).
* ``{retrieved_siblings}`` — Markdown rendering of the chunks retrieved
  from the **wrapper corpus** for the current integration target.
  Replaces ``{wrapper_snapshot}``.

The pre-existing ``format_prompt`` lives in ``skel_ai_lib`` and we keep
it as the single rendering entry point — this module just produces the
strings that get passed in via the ``extra`` dict.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from skel_rag.retriever import RetrievedChunk


# --------------------------------------------------------------------------- #
#  Markdown rendering
# --------------------------------------------------------------------------- #


_NO_CONTEXT_PLACEHOLDER = "_(no relevant context retrieved)_"


def render_retrieved_block(
    chunks: Iterable[RetrievedChunk], *, max_chars: int = 12000
) -> str:
    """Render retrieved chunks as a Markdown block for prompt injection.

    Each chunk becomes a fenced code block headed by
    ``### file:line-line · kind · name``. The total output is capped
    at ``max_chars`` so a runaway top-K result cannot blow the model's
    context window.
    """

    chunks_list: List[RetrievedChunk] = list(chunks)
    if not chunks_list:
        return _NO_CONTEXT_PLACEHOLDER

    parts: List[str] = []
    total = 0
    for chunk in chunks_list:
        body = (
            f"### {chunk.header}\n"
            f"```{chunk.language or ''}\n"
            f"{chunk.source.rstrip()}\n"
            "```\n"
        )
        if total + len(body) > max_chars and parts:
            parts.append("_(further results truncated)_\n")
            break
        parts.append(body)
        total += len(body)
    return "\n".join(parts).strip()


# --------------------------------------------------------------------------- #
#  Query construction
# --------------------------------------------------------------------------- #


_QUERY_PROMPT_PREFIX_CHARS = 600


REFACTOR_SYSTEM_PROMPT = """\
You are a senior software engineer performing a service-local refactor.

Return one or more full-file replacements in this EXACT format:

FILE: relative/path.py
RATIONALE: short explanation
```language
<full file contents>
```

Rules:
- Only edit files inside the current service directory.
- Never use `..`, absolute paths, or `.git` / `.refactor` paths.
- No prose before the first `FILE:` or after the final code fence.
- Keep changes minimal and directly related to the request.

Dev_skel FastAPI layout rules (apply to every refactor in this service):
- `app/wrapper_api/` is wrapper-shared infra (auth, Item/Order/CatalogItem
  tables, WrapperUser). Do NOT add new files here. Do NOT add new
  `table=True` classes here. Do NOT extract enums into new sibling
  files here.
- New domain features (e.g. reservations) go in `app/<feature>/`:
  `__init__.py`, `models.py` (Pydantic + SQLModel table inline; enums
  INLINE, not in a separate file), `routes.py`
  (`router = APIRouter(prefix="/api/<feature>", tags=["<feature>"])`).
- Mount the new router by adding TWO lines to existing `app/routes.py`:
  `from .<feature>.routes import router as <feature>_router`
  `router.include_router(<feature>_router)`
- Sessions: declare ``session: Session = Depends(get_session)``
  with ``from app.wrapper_api.db import get_session``.
- Auth: declare ``user: CurrentUser`` (NO ``Depends()`` wrap — it is
  already an ``Annotated[WrapperUser, Depends(_get_current_user)]``
  alias). Import via ``from app.wrapper_api.deps import CurrentUser``.
- For request bodies, declare a Pydantic ``BaseModel`` and accept it
  as a single typed argument — NEVER pass primitive types directly
  as POST route parameters (they become query params).
- For date/time validation use ``field_validator`` +
  ``date.fromisoformat`` / ``time.fromisoformat`` so bad input gives
  422 (not 500).
"""


REFACTOR_USER_PROMPT = """\
Request:
{request}

Service directory: {service_dir}
Max files: {max_files}

Retrieved context:
{retrieved_context}
"""


def build_query_for_target(
    *,
    target_path: str,
    target_description: str,
    target_prompt: str,
    item_class: str,
    item_name: str,
    items_plural: str,
    service_label: str,
    auth_type: str,
    extras: Optional[Iterable[str]] = None,
) -> str:
    """Build the natural-language query passed to the FAISS retriever.

    The intent is to surface the *kind* of code we're about to generate
    rather than restating the manifest's full instructions. We blend:

    * the target file path (which usually carries the framework idiom
      we want — e.g. ``app/{slug}/routes.py``);
    * the target description (one line of human-readable intent);
    * the start of the manifest prompt (truncated so we don't echo
      thousands of characters into the embedding query);
    * the entity / service / auth labels so retrieval understands the
      vocabulary the user picked.
    """

    extra_bits = " ".join(extras or [])
    prefix = (target_prompt or "").strip()
    if len(prefix) > _QUERY_PROMPT_PREFIX_CHARS:
        prefix = prefix[:_QUERY_PROMPT_PREFIX_CHARS]
    parts = [
        target_path,
        target_description,
        f"entity {item_class} ({item_name}, plural {items_plural})",
        f"service {service_label}",
        f"auth {auth_type}",
        extra_bits,
        prefix,
    ]
    return "\n".join(p for p in parts if p)


def build_query_for_refactor(request: str, ctx: Any) -> str:
    """Build the retriever query for service-local refactors."""

    bits = [
        request.strip(),
        f"service_dir {getattr(ctx, 'service_dir', '')}",
        f"mode {getattr(ctx, 'mode', '')}",
        f"include_siblings {getattr(ctx, 'include_siblings', False)}",
        f"include_skeleton {getattr(ctx, 'include_skeleton', False)}",
    ]
    return "\n".join(str(bit) for bit in bits if bit)
