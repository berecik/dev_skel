"""Standalone CLI for the RAG agent.

The ``skel-rag`` binary is a debugging / introspection tool for the
local FAISS index. The full project generator
(``_bin/skel-gen-ai``) calls into :class:`RagAgent` directly through
the legacy shim — this CLI exists so users can:

* warm up the index for a skeleton (`skel-rag index _skels/python-fastapi-skel`)
* type a free-form query and inspect what the retriever returns
  (`skel-rag search "FastAPI repository CRUD" --path _skels/python-fastapi-skel`)
* see what files would be indexed (`skel-rag info --path _skels/python-fastapi-skel`)
* wipe a stale index (`skel-rag clean --path _skels/python-fastapi-skel`)

Subcommands are deliberately small and stdlib-only at the
argparse level so the CLI starts up instantly even when LangChain is
not installed; the heavy imports happen inside each command's handler.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from skel_rag.config import RagConfig
from skel_rag.corpus import Corpus, corpus_for_skeleton, corpus_for_wrapper

logger = logging.getLogger("skel_rag.cli")


# --------------------------------------------------------------------------- #
#  Argument parsing
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skel-rag",
        description=(
            "Local RAG helper for dev_skel. Build, inspect, and query the "
            "FAISS index used by skel-gen-ai's Ollama prompts."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (repeat for DEBUG)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser(
        "index",
        help="Build / refresh the FAISS index for a skeleton or wrapper",
    )
    p_index.add_argument("path", help="Skeleton directory or wrapper root")
    p_index.add_argument(
        "--rebuild",
        action="store_true",
        help="Discard any cached index before rebuilding",
    )
    p_index.add_argument(
        "--wrapper",
        action="store_true",
        help=(
            "Treat the path as a generated wrapper (index every sibling "
            "service instead of a single skeleton)"
        ),
    )

    p_search = sub.add_parser(
        "search", help="Run a similarity query against an indexed corpus"
    )
    p_search.add_argument("query", help="Natural-language query")
    p_search.add_argument("--path", required=True, help="Corpus root")
    p_search.add_argument(
        "--language",
        help="Limit results to chunks of this language (python/java/typescript/rust/...)",
    )
    p_search.add_argument(
        "-k",
        type=int,
        default=None,
        help="Number of results (defaults to RagConfig.top_k)",
    )
    p_search.add_argument(
        "--wrapper",
        action="store_true",
        help="Treat the path as a generated wrapper",
    )

    p_info = sub.add_parser("info", help="Show information about an indexed corpus")
    p_info.add_argument("--path", required=True, help="Corpus root")
    p_info.add_argument(
        "--wrapper", action="store_true", help="Treat path as a wrapper"
    )

    p_clean = sub.add_parser("clean", help="Delete the cached FAISS index")
    p_clean.add_argument("--path", required=True, help="Corpus root")
    p_clean.add_argument(
        "--wrapper", action="store_true", help="Treat path as a wrapper"
    )

    return parser


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #


def _make_corpus(path_str: str, *, wrapper: bool) -> Corpus:
    path = Path(path_str).expanduser().resolve()
    if not path.is_dir():
        raise SystemExit(f"skel-rag: not a directory: {path}")
    if wrapper:
        return corpus_for_wrapper(path)
    return corpus_for_skeleton(path)


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level, format="%(levelname)s %(name)s: %(message)s"
    )


# --------------------------------------------------------------------------- #
#  Subcommand handlers
# --------------------------------------------------------------------------- #


def _cmd_index(args: argparse.Namespace) -> int:
    from skel_rag.agent import RagAgent

    rag_cfg = RagConfig.from_env()
    corpus = _make_corpus(args.path, wrapper=args.wrapper)
    print(f"Corpus: {corpus.id}")
    print(f"  root  : {corpus.root}")
    print(f"  files : {len(corpus.files)}")

    agent = RagAgent(rag_cfg=rag_cfg)
    retriever = agent.get_retriever(corpus, rebuild=args.rebuild)
    if retriever is None:
        print(
            "skel-rag: retrieval backend unavailable. Install dependencies "
            "via `make install-rag-deps` and try again.",
            file=sys.stderr,
        )
        return 2
    print("Index ready.")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    from skel_rag.agent import RagAgent

    corpus = _make_corpus(args.path, wrapper=args.wrapper)
    agent = RagAgent()
    retriever = agent.get_retriever(corpus)
    if retriever is None:
        print(
            "skel-rag: retrieval backend unavailable. Install dependencies "
            "via `make install-rag-deps` and try again.",
            file=sys.stderr,
        )
        return 2

    chunks = retriever.retrieve(
        args.query, language=args.language, k=args.k
    )
    if not chunks:
        print("(no results)")
        return 0

    for index, chunk in enumerate(chunks, start=1):
        print(f"\n[{index}] {chunk.header}")
        preview = chunk.source.strip().splitlines()[:8]
        for line in preview:
            print(f"    {line}")
        if len(chunk.source.splitlines()) > 8:
            print("    ...")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    from skel_rag.vectorstore import info as store_info

    rag_cfg = RagConfig.from_env()
    corpus = _make_corpus(args.path, wrapper=args.wrapper)
    summary = store_info(corpus, rag_cfg)
    width = max(len(k) for k in summary)
    for key, value in summary.items():
        print(f"  {key:<{width}}  {value}")
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    from skel_rag.vectorstore import clean as store_clean

    rag_cfg = RagConfig.from_env()
    corpus = _make_corpus(args.path, wrapper=args.wrapper)
    removed = store_clean(corpus, rag_cfg)
    if removed:
        print(f"Removed {rag_cfg.index_dirname} from {corpus.root}")
        return 0
    print(f"No cached index found at {corpus.root}/{rag_cfg.index_dirname}")
    return 1


_COMMANDS = {
    "index": _cmd_index,
    "search": _cmd_search,
    "info": _cmd_info,
    "clean": _cmd_clean,
}


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.error(f"Unknown command: {args.command}")
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
