"""Code-aware chunker for the RAG agent.

The chunker turns a single source file into a list of :class:`CodeChunk`
objects (one per top-level definition: function / class / method /
struct / interface / enum / trait / etc.). The metadata each chunk
carries is later embedded as part of the FAISS document so the
retriever can filter by language and reconstruct file:line references
in the prompt.

Languages with first-class chunking:

* **Python** — preferred via tree-sitter, with a stdlib :mod:`ast`
  fallback so the chunker keeps working when tree-sitter is unavailable.
* **Java** — tree-sitter
* **TypeScript / TSX** — tree-sitter
* **JavaScript** — tree-sitter
* **Rust** — tree-sitter

Anything else (Markdown, JSON, .sh, ...) is split with
:class:`RecursiveCharacterTextSplitter` so the FAISS index still has
something to retrieve.

Heavy imports (``tree_sitter``, ``tree_sitter_languages``,
``langchain_text_splitters``) are deferred to first use so importing
this module never forces the deps on callers.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

from skel_rag.config import RagConfig

logger = logging.getLogger("skel_rag.chunker")


# --------------------------------------------------------------------------- #
#  Data classes
# --------------------------------------------------------------------------- #


@dataclass
class CodeChunk:
    """One semantic unit of source code (a function, class, method, ...).

    Attributes:
        file:        Absolute path to the source file.
        rel_path:    Path relative to the corpus root (used in metadata).
        language:    Lower-case language tag (``python``, ``java``,
                     ``typescript``, ``rust``, ``javascript``, …) or
                     ``"text"`` for the fallback splitter.
        kind:        Coarse type of the chunk (``function``, ``class``,
                     ``method``, ``struct``, ``enum``, ``trait``,
                     ``interface``, ``module``, ``text_chunk``, …).
        name:        Best-effort identifier for the chunk
                     (``""`` for fallback chunks or anonymous nodes).
        start_line:  1-indexed first line of the chunk in the source.
        end_line:    1-indexed last line of the chunk in the source.
        source:      The chunk's text content.
    """

    file: Path
    rel_path: str
    language: str
    kind: str
    name: str
    start_line: int
    end_line: int
    source: str

    def to_metadata(self, *, corpus_id: str) -> dict:
        """Return the metadata dict embedded into the FAISS document."""

        return {
            "corpus_id": corpus_id,
            "file": str(self.file),
            "rel_path": self.rel_path,
            "language": self.language,
            "kind": self.kind,
            "name": self.name,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


# --------------------------------------------------------------------------- #
#  Language detection
# --------------------------------------------------------------------------- #


# Map file extension → (language tag, tree-sitter parser name).
# tree-sitter-languages exposes a single parser per language, but for
# TS/TSX we still want the metadata to read ``typescript`` (the parser is
# the same; the JSX-aware variant is `tsx`).
_EXT_TO_LANG: dict[str, tuple[str, str]] = {
    ".py": ("python", "python"),
    ".java": ("java", "java"),
    ".ts": ("typescript", "typescript"),
    ".tsx": ("typescript", "tsx"),
    ".js": ("javascript", "javascript"),
    ".jsx": ("javascript", "javascript"),
    ".mjs": ("javascript", "javascript"),
    ".cjs": ("javascript", "javascript"),
    ".rs": ("rust", "rust"),
    ".go": ("go", "go"),
    ".c": ("c", "c"),
    ".h": ("c", "c"),
    ".cpp": ("cpp", "cpp"),
    ".cc": ("cpp", "cpp"),
    ".cxx": ("cpp", "cpp"),
    ".hpp": ("cpp", "cpp"),
    ".cs": ("csharp", "c_sharp"),
    ".dart": ("dart", "dart"),
}


# Per-language node types we want to emit as standalone chunks.  These were
# pulled from each grammar's ``node-types.json`` and verified against the
# tree-sitter playground.  The "kind" assigned to each node is whatever
# reads naturally in retrieval metadata.
_NODE_KINDS: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
        "decorated_definition": "function",
    },
    "java": {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "record_declaration": "record",
        "enum_declaration": "enum",
        "method_declaration": "method",
        "constructor_declaration": "constructor",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
        "enum_declaration": "enum",
        "method_definition": "method",
        "lexical_declaration": "binding",  # top-level `const X = ...`
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "lexical_declaration": "binding",
    },
    "rust": {
        "function_item": "function",
        "impl_item": "impl",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
        "mod_item": "module",
        "type_item": "type",
        "const_item": "const",
        "static_item": "static",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
        "type_declaration": "type",
    },
    "c": {
        "function_definition": "function",
        "struct_specifier": "struct",
        "enum_specifier": "enum",
    },
    "cpp": {
        "function_definition": "function",
        "class_specifier": "class",
        "struct_specifier": "struct",
        "enum_specifier": "enum",
    },
    "csharp": {
        "method_declaration": "method",
        "class_declaration": "class",
        "interface_declaration": "interface",
        "struct_declaration": "struct",
        "enum_declaration": "enum",
        "record_declaration": "record",
    },
    "dart": {
        # Top-level definitions emitted by the tree-sitter Dart grammar.
        # `function_signature` covers free functions; `class_definition`
        # / `mixin_declaration` / `extension_declaration` /
        # `enum_declaration` cover the four named-type forms; the
        # member-level node names cover methods + getters/setters
        # inside class bodies.
        "class_definition": "class",
        "mixin_declaration": "mixin",
        "extension_declaration": "extension",
        "enum_declaration": "enum",
        "function_signature": "function",
        "method_signature": "method",
        "getter_signature": "getter",
        "setter_signature": "setter",
        "constructor_signature": "constructor",
    },
}


def detect_language(path: Path) -> Optional[tuple[str, str]]:
    """Return ``(language_tag, parser_name)`` for *path*, or ``None``."""

    return _EXT_TO_LANG.get(path.suffix.lower())


# --------------------------------------------------------------------------- #
#  Tree-sitter parser cache
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=None)
def _get_parser(parser_name: str) -> Optional[Any]:
    """Load a tree-sitter parser, returning ``None`` if unavailable.

    Tries ``tree_sitter_languages`` first (the most portable distribution
    that ships prebuilt wheels for macOS arm64 + Linux), then falls back
    to ``tree_sitter_language_pack`` (a maintained fork some platforms
    require). Both packages expose ``get_parser(name)`` with identical
    semantics so callers do not need to know which one is installed.
    """

    try:
        from tree_sitter_languages import get_parser  # type: ignore
    except ImportError:
        try:
            from tree_sitter_language_pack import get_parser  # type: ignore
        except ImportError:
            logger.warning(
                "Neither tree_sitter_languages nor tree_sitter_language_pack "
                "is installed; falling back to stdlib chunking. Run "
                "`make install-rag-deps` to enable code-aware chunking."
            )
            return None

    try:
        return get_parser(parser_name)
    except Exception as exc:  # noqa: BLE001 — surface a single warning
        logger.warning(
            "tree-sitter parser for %r could not be loaded: %s. "
            "Falling back to text splitting for that language.",
            parser_name,
            exc,
        )
        return None


# --------------------------------------------------------------------------- #
#  Chunker
# --------------------------------------------------------------------------- #


class CodeChunker:
    """Turn source files into a stream of :class:`CodeChunk` objects.

    The chunker is intentionally stateless apart from the ``RagConfig``
    knobs (max chunk size + fallback splitter parameters), so callers
    can keep one instance per process and reuse it across corpora.
    """

    def __init__(self, rag_cfg: Optional[RagConfig] = None) -> None:
        self.cfg = rag_cfg or RagConfig.from_env()
        self._fallback_splitter: Optional[Any] = None

    # ---- public API -------------------------------------------------------

    def chunk_file(self, path: Path, *, corpus_root: Path) -> List[CodeChunk]:
        """Return all :class:`CodeChunk` instances for *path*.

        ``corpus_root`` is used to compute the chunk's ``rel_path`` so
        the FAISS metadata stays portable across machines.
        """

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("skipping %s: %s", path, exc)
            return []

        if not source.strip():
            return []

        rel_path = self._rel_path(path, corpus_root)
        detected = detect_language(path)
        if detected is None:
            return self._chunk_text(path, rel_path, source, language="text")

        language, parser_name = detected

        # Tree-sitter is the preferred path for everything we recognise.
        chunks = self._chunk_with_tree_sitter(
            path=path,
            rel_path=rel_path,
            source=source,
            language=language,
            parser_name=parser_name,
        )
        if chunks:
            return chunks

        # Stdlib `ast` is a robust fallback for Python only.  For every
        # other language we degrade to recursive text splitting so the
        # FAISS index still gets some signal.
        if language == "python":
            chunks = self._chunk_python_with_stdlib(path, rel_path, source)
            if chunks:
                return chunks

        return self._chunk_text(path, rel_path, source, language=language)

    # ---- tree-sitter ------------------------------------------------------

    def _chunk_with_tree_sitter(
        self,
        *,
        path: Path,
        rel_path: str,
        source: str,
        language: str,
        parser_name: str,
    ) -> List[CodeChunk]:
        parser = _get_parser(parser_name)
        if parser is None:
            return []

        try:
            tree = parser.parse(source.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("tree-sitter parse failed for %s: %s", path, exc)
            return []

        kinds = _NODE_KINDS.get(language, {})
        if not kinds:
            return []

        source_bytes = source.encode("utf-8")
        chunks: List[CodeChunk] = []
        self._walk_tree_sitter(
            node=tree.root_node,
            kinds=kinds,
            source_bytes=source_bytes,
            path=path,
            rel_path=rel_path,
            language=language,
            out=chunks,
        )

        # Make sure we never return an empty result for a non-empty file:
        # if the tree had nothing we recognise, fall back to text splitting
        # so the file is still indexed.
        return chunks

    def _walk_tree_sitter(
        self,
        *,
        node: Any,
        kinds: dict[str, str],
        source_bytes: bytes,
        path: Path,
        rel_path: str,
        language: str,
        out: List[CodeChunk],
    ) -> None:
        """Depth-first walk that records chunks for every recognised node.

        We collect *both* top-level definitions AND their nested methods
        so retrieval surfaces individual methods rather than entire
        classes when the question is method-specific. Anonymous /
        unnameable nodes get an empty ``name`` which the prompt
        renderer is fine with.
        """

        node_kind = kinds.get(node.type)
        if node_kind is not None:
            chunk = self._node_to_chunk(
                node=node,
                node_kind=node_kind,
                source_bytes=source_bytes,
                path=path,
                rel_path=rel_path,
                language=language,
            )
            if chunk is not None:
                out.append(chunk)

        for child in node.children:
            self._walk_tree_sitter(
                node=child,
                kinds=kinds,
                source_bytes=source_bytes,
                path=path,
                rel_path=rel_path,
                language=language,
                out=out,
            )

    def _node_to_chunk(
        self,
        *,
        node: Any,
        node_kind: str,
        source_bytes: bytes,
        path: Path,
        rel_path: str,
        language: str,
    ) -> Optional[CodeChunk]:
        start_byte = node.start_byte
        end_byte = node.end_byte
        if end_byte <= start_byte:
            return None

        text = source_bytes[start_byte:end_byte].decode("utf-8", errors="replace")
        if not text.strip():
            return None

        # Cap individual chunks so a 5000-line generated file can't drown
        # the embedder. The truncation is at the byte level which keeps
        # the chunk a valid string and is fine for retrieval purposes.
        max_chars = self.cfg.chunk_max_chars
        truncated = text if len(text) <= max_chars else text[:max_chars] + "\n# ... (chunk truncated)\n"

        name = self._extract_node_name(node, source_bytes) or ""

        return CodeChunk(
            file=path,
            rel_path=rel_path,
            language=language,
            kind=node_kind,
            name=name,
            # tree-sitter rows are 0-indexed; humans expect 1-indexed.
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            source=truncated,
        )

    @staticmethod
    def _extract_node_name(node: Any, source_bytes: bytes) -> Optional[str]:
        """Best-effort identifier extraction.

        Most grammars expose a ``name`` field on definitions, which
        ``child_by_field_name`` retrieves directly. The ``decorated_definition``
        node in Python is special: it wraps a function/class node and we
        need to recurse one level. Failing that we walk the immediate
        children for an ``identifier`` / ``type_identifier`` token.
        """

        try:
            named = node.child_by_field_name("name")
        except Exception:  # noqa: BLE001
            named = None

        if named is None and node.type == "decorated_definition":
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    try:
                        named = child.child_by_field_name("name")
                    except Exception:  # noqa: BLE001
                        named = None
                    if named is not None:
                        break

        if named is not None:
            return source_bytes[named.start_byte : named.end_byte].decode(
                "utf-8", errors="replace"
            )

        for child in node.children:
            if child.type in ("identifier", "type_identifier"):
                return source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="replace"
                )
        return None

    # ---- python stdlib fallback ------------------------------------------

    def _chunk_python_with_stdlib(
        self, path: Path, rel_path: str, source: str
    ) -> List[CodeChunk]:
        """Use ``ast`` to chunk Python when tree-sitter is unavailable.

        This is a strict subset of what the tree-sitter path produces but
        it keeps the chunker functional in environments that lack the
        prebuilt grammar wheels (e.g. exotic Python versions).
        """

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.debug("ast.parse failed for %s: %s", path, exc)
            return []

        lines = source.splitlines()
        chunks: List[CodeChunk] = []

        def emit(node: ast.AST, kind: str, name: str) -> None:
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            text = "\n".join(lines[start - 1 : end])
            if not text.strip():
                return
            max_chars = self.cfg.chunk_max_chars
            if len(text) > max_chars:
                text = text[:max_chars] + "\n# ... (chunk truncated)\n"
            chunks.append(
                CodeChunk(
                    file=path,
                    rel_path=rel_path,
                    language="python",
                    kind=kind,
                    name=name,
                    start_line=start,
                    end_line=end,
                    source=text,
                )
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                emit(node, "function", node.name)
            elif isinstance(node, ast.FunctionDef):
                emit(node, "function", node.name)
            elif isinstance(node, ast.ClassDef):
                emit(node, "class", node.name)

        return chunks

    # ---- recursive character splitter fallback ---------------------------

    def _chunk_text(
        self, path: Path, rel_path: str, source: str, *, language: str
    ) -> List[CodeChunk]:
        """Split *source* into overlapping windows for indexing.

        Used for unknown languages and as a final fallback when
        tree-sitter / stdlib parsing both fail. The text splitter comes
        from ``langchain-text-splitters``; if that package is missing we
        emit one chunk per file as a last resort so the index never ends
        up empty.
        """

        splitter = self._get_fallback_splitter()
        if splitter is None:
            return [
                CodeChunk(
                    file=path,
                    rel_path=rel_path,
                    language=language,
                    kind="text_chunk",
                    name="",
                    start_line=1,
                    end_line=max(1, source.count("\n") + 1),
                    source=source[: self.cfg.chunk_max_chars],
                )
            ]

        pieces = splitter.split_text(source)
        chunks: List[CodeChunk] = []
        cursor = 1
        for piece in pieces:
            line_count = max(1, piece.count("\n") + 1)
            chunks.append(
                CodeChunk(
                    file=path,
                    rel_path=rel_path,
                    language=language,
                    kind="text_chunk",
                    name="",
                    start_line=cursor,
                    end_line=cursor + line_count - 1,
                    source=piece,
                )
            )
            cursor += line_count
        return chunks

    def _get_fallback_splitter(self) -> Optional[Any]:
        if self._fallback_splitter is not None:
            return self._fallback_splitter
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            logger.warning(
                "langchain-text-splitters is not installed; falling back to "
                "single-chunk indexing for unknown file types. Run "
                "`make install-rag-deps` to enable proper splitting."
            )
            return None
        self._fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.cfg.fallback_chunk_size,
            chunk_overlap=self.cfg.fallback_chunk_overlap,
        )
        return self._fallback_splitter

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _rel_path(path: Path, corpus_root: Path) -> str:
        try:
            return str(path.resolve().relative_to(corpus_root.resolve()))
        except ValueError:
            return str(path)


# --------------------------------------------------------------------------- #
#  Convenience helpers
# --------------------------------------------------------------------------- #


def chunks_to_documents(
    chunks: Iterable[CodeChunk], *, corpus_id: str
) -> List[Any]:
    """Convert :class:`CodeChunk` objects into LangChain ``Document`` objects.

    The import of ``langchain_core.documents.Document`` is deferred so
    callers that only want raw chunks (e.g. unit tests) can run without
    LangChain installed.
    """

    from langchain_core.documents import Document  # local import on purpose

    documents: List[Document] = []
    for chunk in chunks:
        documents.append(
            Document(
                page_content=_format_document_text(chunk),
                metadata=chunk.to_metadata(corpus_id=corpus_id),
            )
        )
    return documents


def _format_document_text(chunk: CodeChunk) -> str:
    """Render a chunk as the text body the embedder will see.

    We prepend a small header so the embedding model has structural
    context (file path, kind, name) in addition to the raw source. This
    consistently improves retrieval quality on small models like
    bge-small without bloating the index.
    """

    header_bits = [chunk.rel_path]
    if chunk.kind:
        header_bits.append(chunk.kind)
    if chunk.name:
        header_bits.append(chunk.name)
    header = " · ".join(header_bits)
    return f"{header}\n{chunk.source}"


def chunk_files(
    paths: Sequence[Path],
    *,
    corpus_root: Path,
    rag_cfg: Optional[RagConfig] = None,
) -> List[CodeChunk]:
    """Convenience: chunk every path in *paths* with one chunker."""

    chunker = CodeChunker(rag_cfg)
    out: List[CodeChunk] = []
    for path in paths:
        out.extend(chunker.chunk_file(path, corpus_root=corpus_root))
    return out
