"""High-level RAG agent.

The :class:`RagAgent` is the only object the legacy shim
(``_bin/skel_ai_lib.py``) and the standalone CLI
(``_bin/skel-rag``) need to interact with. It encapsulates:

* the active :class:`OllamaConfig` and :class:`RagConfig`;
* a (lazily loaded) embeddings model;
* a small per-corpus FAISS retriever cache so the per-target loop does
  not rebuild the index for every file;
* the per-target / integration / fix-loop orchestration that previously
  lived as free functions in ``skel_ai_lib.py``.

The agent is **dependency-tolerant**: when LangChain / FAISS / the
embedding model are not installed, retrieval is skipped and the agent
falls back to the legacy "stuff the reference template into the prompt"
strategy. That keeps every manifest using ``{template}`` /
``{wrapper_snapshot}`` working unchanged on machines without the new
dependencies, and only manifests that opt into ``{retrieved_context}``
require the install.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from skel_rag.config import OllamaConfig, RagConfig
from skel_rag.corpus import Corpus, corpus_for_skeleton, corpus_for_wrapper
from skel_rag.llm import OllamaError, chat as llm_chat
from skel_rag.prompts import build_query_for_target, render_retrieved_block
from skel_rag.retriever import RetrievedChunk, Retriever

if TYPE_CHECKING:  # pragma: no cover
    from skel_ai_lib import (  # noqa: F401
        AiManifest,
        AiTarget,
        GenerationContext,
        IntegrationManifest,
        TargetResult,
        TestRunResult,
    )

logger = logging.getLogger("skel_rag.agent")


_NO_RETRIEVAL_PLACEHOLDER = "_(retrieval disabled — install dependencies via `make install-rag-deps`)_"


class RagAgent:
    """Stateful orchestrator that wires retrieval into the Ollama pipeline."""

    def __init__(
        self,
        ollama_cfg: Optional[OllamaConfig] = None,
        rag_cfg: Optional[RagConfig] = None,
    ) -> None:
        self.ollama_cfg = ollama_cfg or OllamaConfig.from_env()
        self.rag_cfg = rag_cfg or RagConfig.from_env()
        self._embeddings: Any = None
        self._embeddings_failed = False
        self._retriever_cache: Dict[Tuple[str, str], Retriever] = {}

    # ---- public chat helper ----------------------------------------------

    def chat(self, system: str, user: str) -> str:
        """Forward a system + user turn to Ollama via LangChain."""

        return llm_chat(self.ollama_cfg, system, user)

    # ---- retrieval --------------------------------------------------------

    def get_retriever(
        self,
        corpus: Corpus,
        *,
        rebuild: bool = False,
        persist: bool = True,
    ) -> Optional[Retriever]:
        """Return a :class:`Retriever` for *corpus* (cached, lazy build).

        Returns ``None`` when the RAG stack is unavailable; callers
        treat that as "skip retrieval, fall back to legacy placeholders".
        """

        cache_key = (corpus.id, str(corpus.root))
        cached = self._retriever_cache.get(cache_key)
        if cached is not None and not rebuild:
            return cached

        embeddings = self._get_embeddings()
        if embeddings is None:
            return None

        try:
            from skel_rag.vectorstore import load_or_build, VectorStoreError
        except ImportError:  # pragma: no cover — handled by ImportError below
            logger.warning("vectorstore module unavailable; disabling retrieval")
            return None

        try:
            store = load_or_build(
                corpus,
                self.rag_cfg,
                embeddings,
                rebuild=rebuild,
                persist=persist,
            )
        except VectorStoreError as exc:
            logger.warning("could not build FAISS index for %s: %s", corpus.id, exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "unexpected error building index for %s: %s", corpus.id, exc
            )
            return None

        retriever = Retriever(store, self.rag_cfg)
        self._retriever_cache[cache_key] = retriever
        return retriever

    def _get_embeddings(self) -> Any:
        if self._embeddings is not None:
            return self._embeddings
        if self._embeddings_failed:
            return None
        try:
            from skel_rag.embedder import EmbeddingError, make_embeddings
        except ImportError:
            self._embeddings_failed = True
            return None
        try:
            self._embeddings = make_embeddings(self.rag_cfg)
        except EmbeddingError as exc:
            logger.warning("embedding backend unavailable: %s", exc)
            self._embeddings_failed = True
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("unexpected error loading embedder: %s", exc)
            self._embeddings_failed = True
            return None
        return self._embeddings

    # ---- per-target phase -------------------------------------------------

    def generate_targets(
        self,
        *,
        manifest: "AiManifest",
        ctx: "GenerationContext",
        dry_run: bool = False,
        progress: Any = None,
    ) -> List["TargetResult"]:
        """RAG-aware replacement for ``skel_ai_lib.generate_targets``.

        Indexes the **skeleton** at ``ctx.skeleton_path`` once, then for
        every manifest target retrieves the most relevant chunks and
        passes them to the prompt renderer alongside the legacy
        ``{template}`` placeholder.
        """

        from skel_ai_lib import (  # local import to avoid circular dependency
            AiManifest as _AiManifest,  # noqa: F401
            TargetResult,
            build_system_prompt,
            clean_response,
            expand_target_paths,
            format_prompt,
            _read_reference,
        )

        results: List[TargetResult] = []
        system = build_system_prompt(manifest, ctx)
        retriever = self.get_retriever(corpus_for_skeleton(ctx.skeleton_path))

        for index, target in enumerate(manifest.targets, start=1):
            expanded = expand_target_paths(target, ctx)
            label = expanded.description or expanded.path
            if progress is not None:
                progress.write(
                    f"  [{index}/{len(manifest.targets)}] {label}\n"
                )

            reference = _read_reference(ctx.skeleton_path, expanded.template)
            retrieved_block = self._retrieve_block_for_target(
                retriever=retriever,
                target=expanded,
                ctx=ctx,
            )

            user_prompt = format_prompt(
                target.prompt,
                ctx,
                reference=reference,
                extra={"retrieved_context": retrieved_block},
            )

            destination = ctx.project_dir / expanded.path

            if dry_run:
                results.append(
                    TargetResult(
                        target=expanded,
                        written_to=destination,
                        bytes_written=0,
                    )
                )
                continue

            raw = self.chat(system=system, user=user_prompt)
            cleaned = clean_response(raw, target.language)

            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(cleaned, encoding="utf-8")

            results.append(
                TargetResult(
                    target=expanded,
                    written_to=destination,
                    bytes_written=len(cleaned.encode("utf-8")),
                )
            )

        return results

    # ---- integration phase ------------------------------------------------

    def run_integration_phase(
        self,
        *,
        manifest: "IntegrationManifest",
        ctx: "GenerationContext",
        dry_run: bool = False,
        progress: Any = None,
    ) -> List["TargetResult"]:
        """RAG-aware replacement for ``skel_ai_lib.run_integration_phase``.

        Builds an *ephemeral* wrapper-level corpus (not persisted to
        disk) so retrieval over sibling services replaces the legacy
        full-file ``{wrapper_snapshot}`` blob.
        """

        from skel_ai_lib import (  # local import — avoid circular dependency
            AiManifest as LegacyAiManifest,
            TargetResult,
            build_system_prompt,
            clean_response,
            expand_target_paths,
            format_prompt,
            _read_reference,
        )

        if not manifest.targets:
            if progress is not None:
                progress.write(
                    "  (integration manifest has no targets — nothing to do)\n"
                )
            return []

        results: List[TargetResult] = []
        try:
            system = build_system_prompt(
                LegacyAiManifest(
                    skeleton_name=manifest.skeleton_name,
                    targets=[],
                    system_prompt=manifest.system_prompt,
                    notes=manifest.notes,
                ),
                ctx,
            )
        except Exception as exc:  # noqa: BLE001 — bypass to retry-friendly state
            if progress is not None:
                progress.write(
                    f"  (integration system prompt render failed: {exc!r}; "
                    "skipping the integration phase)\n"
                )
            return []

        # Wrapper corpus is the parent directory of the new service.
        wrapper_root = ctx.project_root
        wrapper_corpus = corpus_for_wrapper(
            wrapper_root, exclude_slug=ctx.service_subdir
        )
        wrapper_retriever = self.get_retriever(
            wrapper_corpus, persist=False
        ) if wrapper_corpus.files else None

        for index, target in enumerate(manifest.targets, start=1):
            try:
                expanded = expand_target_paths(target, ctx)
            except Exception as exc:  # noqa: BLE001
                if progress is not None:
                    progress.write(
                        f"  [int {index}/{len(manifest.targets)}] "
                        f"(skipping — path expansion failed: {exc})\n"
                    )
                continue

            label = expanded.description or expanded.path
            if progress is not None:
                progress.write(
                    f"  [int {index}/{len(manifest.targets)}] {label}\n"
                )

            try:
                reference = _read_reference(ctx.skeleton_path, expanded.template)
                retrieved_siblings_block = self._retrieve_block_for_target(
                    retriever=wrapper_retriever,
                    target=expanded,
                    ctx=ctx,
                )
                user_prompt = format_prompt(
                    target.prompt,
                    ctx,
                    reference=reference,
                    extra={
                        "retrieved_context": retrieved_siblings_block,
                        "retrieved_siblings": retrieved_siblings_block,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                if progress is not None:
                    progress.write(
                        f"      (skipping — prompt render failed: {exc})\n"
                    )
                continue

            destination = ctx.project_dir / expanded.path
            if dry_run:
                results.append(
                    TargetResult(
                        target=expanded,
                        written_to=destination,
                        bytes_written=0,
                    )
                )
                continue

            try:
                raw = self.chat(system=system, user=user_prompt)
            except OllamaError as exc:
                if progress is not None:
                    progress.write(
                        f"      (Ollama error on integration target: {exc}; "
                        "continuing to next target)\n"
                    )
                continue
            except Exception as exc:  # noqa: BLE001
                if progress is not None:
                    progress.write(
                        f"      (unexpected Ollama failure: {exc!r}; "
                        "continuing to next target)\n"
                    )
                continue

            cleaned = clean_response(raw, target.language)
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(cleaned, encoding="utf-8")
            except OSError as exc:
                if progress is not None:
                    progress.write(
                        f"      (could not write {destination}: {exc}; skipping)\n"
                    )
                continue

            results.append(
                TargetResult(
                    target=expanded,
                    written_to=destination,
                    bytes_written=len(cleaned.encode("utf-8")),
                )
            )

        return results

    # ---- fix loop ---------------------------------------------------------

    def fix_target(
        self,
        *,
        target_result: "TargetResult",
        test_run: "TestRunResult",
        test_command: str,
        ctx: "GenerationContext",
    ) -> str:
        """RAG-aware replacement for ``skel_ai_lib._ask_ollama_to_fix``.

        Uses the wrapper-level retriever to surface sibling code that
        the failing file is most likely to depend on. The model still
        receives the full failing file (it has to — patches are not in
        scope) plus a smaller block of retrieved sibling context.
        """

        from skel_ai_lib import (  # noqa: F401 — circular avoidance
            _FIX_SYSTEM_PROMPT,
            _FIX_USER_PROMPT,
            clean_response,
            format_prompt,
        )

        file_path = target_result.written_to
        try:
            current_contents = file_path.read_text(encoding="utf-8")
        except OSError:
            current_contents = ""

        try:
            rel_path = file_path.relative_to(ctx.project_dir)
        except ValueError:
            rel_path = file_path

        wrapper_corpus = corpus_for_wrapper(
            ctx.project_root, exclude_slug=ctx.service_subdir
        )
        wrapper_retriever = (
            self.get_retriever(wrapper_corpus, persist=False)
            if wrapper_corpus.files
            else None
        )
        retrieved_block = self._retrieve_block_for_target(
            retriever=wrapper_retriever,
            target=target_result.target,
            ctx=ctx,
            extras=[
                f"failing test exit code {test_run.returncode}",
                target_result.target.path,
            ],
        )

        system = format_prompt(_FIX_SYSTEM_PROMPT, ctx)
        user = format_prompt(
            _FIX_USER_PROMPT,
            ctx,
            reference=None,
            extra={
                "rel_path": str(rel_path),
                "language": target_result.target.language,
                "current_contents": current_contents,
                "test_command": test_command,
                "returncode": test_run.returncode,
                "test_output": test_run.combined_output(),
                "retrieved_context": retrieved_block,
                "retrieved_siblings": retrieved_block,
            },
        )
        raw = self.chat(system=system, user=user)
        return clean_response(raw, target_result.target.language)

    # ---- internals --------------------------------------------------------

    def _retrieve_block_for_target(
        self,
        *,
        retriever: Optional[Retriever],
        target: "AiTarget",
        ctx: "GenerationContext",
        extras: Optional[List[str]] = None,
    ) -> str:
        if retriever is None:
            return _NO_RETRIEVAL_PLACEHOLDER

        query = build_query_for_target(
            target_path=target.path,
            target_description=target.description or "",
            target_prompt=target.prompt or "",
            item_class=ctx.item_class,
            item_name=ctx.item_name,
            items_plural=ctx.items_plural,
            service_label=ctx.service_label,
            auth_type=ctx.auth_type,
            extras=extras,
        )
        chunks: List[RetrievedChunk] = retriever.retrieve(
            query, language=target.language or None
        )
        return render_retrieved_block(
            chunks, max_chars=self.rag_cfg.max_context_chars
        )
