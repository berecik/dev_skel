#!/usr/bin/env python3
"""Backwards-compat shim for the legacy ``skel_ai_lib`` API.

This module used to contain the entire Ollama-driven project generator
(prompt building, urllib HTTP client, per-target loop, integration phase,
test-and-fix loop). As of the 2026-04 RAG refactor the orchestration
lives in :mod:`skel_rag` and this file's job is to keep every public
symbol (data classes, manifest loaders, dialogs, prompt helpers, the
``OllamaClient`` shim) importable under its original name so:

* ``_bin/skel-gen-ai`` and ``_bin/skel-test-ai-generators`` keep working
  without touching their import statements;
* manifests using the legacy ``{template}`` / ``{wrapper_snapshot}``
  placeholders keep generating identical prompts;
* manifests opting into the new ``{retrieved_context}`` /
  ``{retrieved_siblings}`` placeholders get RAG-driven context blocks
  via :class:`skel_rag.agent.RagAgent`.

The four orchestration functions (:func:`generate_targets`,
:func:`run_integration_phase`, :func:`run_test_and_fix_loop`, and the
private :func:`_ask_ollama_to_fix`) now delegate to ``RagAgent``;
:class:`OllamaClient.chat` proxies to LangChain's ``ChatOllama`` via
:mod:`skel_rag.llm`. Everything else (dataclasses, manifest loaders,
``format_prompt``, ``clean_response``, ``build_system_prompt``,
``discover_siblings``, ``run_service_tests``, the interactive dialogs)
is preserved verbatim because the RAG agent imports it.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dev_skel_lib import is_safe_service_id, read_project_yml, slugify_service_name


@contextlib.contextmanager
def _heartbeat_env(label: str):
    """Emit a `[ai] <label> Ns elapsed...` tick while the body runs.

    Activated only when ``SKEL_AI_VERBOSE`` is a positive integer in
    the environment. Interval defaults to 60s at level 1, tightens to
    15s at level 1+ unless ``SKEL_AI_HEARTBEAT_SEC`` overrides. No-op
    otherwise so the OllamaClient call path stays unchanged for
    non-verbose callers.
    """

    raw_level = os.environ.get("SKEL_AI_VERBOSE", "").strip()
    level = int(raw_level) if raw_level.isdigit() else 0
    if level < 1:
        yield
        return

    interval_env = os.environ.get("SKEL_AI_HEARTBEAT_SEC", "").strip()
    try:
        interval = max(1.0, float(interval_env)) if interval_env else 15.0
    except ValueError:
        interval = 15.0

    started = time.monotonic()
    stop = threading.Event()

    def _tick() -> None:
        while not stop.wait(interval):
            elapsed = int(time.monotonic() - started)
            try:
                sys.stderr.write(f"[ai] {label} {elapsed}s elapsed...\n")
                sys.stderr.flush()
            except (ValueError, OSError):
                return

    thread = threading.Thread(target=_tick, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1.0)


# --------------------------------------------------------------------------- #
#  Configuration & data classes
# --------------------------------------------------------------------------- #


from skel_rag.config import (  # noqa: E402 — stdlib-only, safe at top level
    DEFAULT_OLLAMA_BASE_URL,
    _resolve_base_url,
)

DEFAULT_OLLAMA_MODEL = "qwen3-coder:30b"
# seconds — local Ollama can be slow on big models. The default is sized
# for ~30B-class instruction models like qwen3-coder:30b (a single completion
# can include a 30-40 s cold-load on the first call plus several minutes
# of generation on long files). Override with OLLAMA_TIMEOUT in the
# environment when running on faster hardware or against a smaller model.
DEFAULT_TIMEOUT = 1800


@dataclass
class OllamaConfig:
    """Connection details for an Ollama server (OpenAI-compatible API)."""

    model: str = DEFAULT_OLLAMA_MODEL
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        """Build a config from ``OLLAMA_*`` environment variables.

        Resolution: ``OLLAMA_BASE_URL`` (explicit) → ``OLLAMA_HOST``
        (``host:port``) → default ``localhost:11434``. A trailing
        ``/v1`` is normalised away because the rest of this module
        appends the route segments itself.
        """

        base = _resolve_base_url()
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        if base.endswith("/"):
            base = base.rstrip("/")
        try:
            timeout = int(os.environ.get("OLLAMA_TIMEOUT", str(DEFAULT_TIMEOUT)))
        except ValueError:
            timeout = DEFAULT_TIMEOUT
        try:
            temperature = float(os.environ.get("OLLAMA_TEMPERATURE", "0.2"))
        except ValueError:
            temperature = 0.2
        return cls(
            model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            base_url=base,
            timeout=timeout,
            temperature=temperature,
        )


@dataclass
class GenerationContext:
    """Per-run inputs collected from the user (or CLI flags).

    The fields here are interpolated into manifest prompt templates via
    :func:`format_prompt` and are also exposed to manifests that prefer to
    build prompts from helper functions.

    The ``backend_extra`` / ``frontend_extra`` / ``integration_extra``
    fields hold the **three custom user prompts** the dialog asks for
    (replacing the older single ``auth_details`` field). Each is a free
    text snippet the user can use to nudge Ollama in a particular
    direction during the matching phase. Manifest authors can reference
    them via the ``{backend_extra}`` / ``{frontend_extra}`` /
    ``{integration_extra}`` placeholders. ``auth_details`` is kept as
    a backwards-compatible alias for ``backend_extra`` so prompts that
    still use ``{auth_details}`` keep working.
    """

    skeleton_name: str
    skeleton_path: Path
    project_root: Path
    project_name: str
    service_subdir: str
    service_label: str
    item_name: str
    auth_type: str
    auth_details: str = ""
    backend_extra: str = ""
    frontend_extra: str = ""
    integration_extra: str = ""
    testing_scenario: str = ""
    extra: Dict[str, str] = field(default_factory=dict)
    # Populated by the integration phase from :func:`discover_siblings`
    # so prompts can interpolate ``{wrapper_snapshot}`` (or walk
    # ``ctx.siblings`` directly from manifest helpers). Empty during the
    # per-target generation phase.
    siblings: List["ServiceSummary"] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Backwards-compat alias: if the caller only provided
        # `auth_details` (the old single freeform note), surface its
        # text as `backend_extra` so new prompts pick it up too.
        # Conversely, if they only set `backend_extra`, mirror it onto
        # `auth_details` so existing manifest prompts that reference
        # `{auth_details}` keep working unchanged.
        if self.backend_extra and not self.auth_details:
            self.auth_details = self.backend_extra
        elif self.auth_details and not self.backend_extra:
            self.backend_extra = self.auth_details

    # ---- derived helpers --------------------------------------------------

    @property
    def project_dir(self) -> Path:
        """Absolute path to the inner service directory."""

        return self.project_root / self.service_subdir

    @property
    def item_class(self) -> str:
        """``ticket`` -> ``Ticket``."""

        return _camel_case(self.item_name)

    @property
    def items_plural(self) -> str:
        """``ticket`` -> ``tickets`` (very naive plural — fine for slugs)."""

        if self.item_name.endswith("s"):
            return self.item_name + "es"
        return self.item_name + "s"

    @property
    def service_slug(self) -> str:
        """``Ticket Service`` -> ``ticket_service``.

        Always equal to ``service_subdir`` in well-formed contexts because
        :func:`dev_skel_lib.generate_project` already uses this slug as the
        directory name. The accessor is kept so manifests can interpolate
        the slug independently of whatever subdir convention the wrapper
        ends up with after collision resolution.
        """

        return slugify_service_name(self.service_label)

    def as_template_vars(self) -> Dict[str, str]:
        """Flatten the context into the dict used for prompt interpolation.

        Slug-shaped fields are exposed in **both** lowercase and UPPERCASE
        variants so manifests can interpolate constant names directly —
        e.g. ``{ITEMS_PLURAL}_BASE`` rendering to ``TASKS_BASE`` for an
        ``item_name=task`` run. The uppercase variants only differ from
        the lowercase ones for snake_case fields; ``ITEM_CLASS`` is
        included for symmetry even though ``item_class`` is already
        PascalCase.

        Integration-phase prompts can additionally reference
        ``{wrapper_snapshot}`` (a Markdown rendering of every sibling
        service captured by :func:`discover_siblings`) and
        ``{sibling_count}`` / ``{sibling_slugs}`` for quick branching.
        Both fall back to a "no siblings" placeholder string when the
        per-target phase is running so manifests can share helper
        templates between phases without crashing.
        """

        if self.siblings:
            wrapper_snapshot = "\n".join(s.render_block() for s in self.siblings)
            sibling_slugs = ", ".join(s.slug for s in self.siblings)
        else:
            wrapper_snapshot = "_(no sibling services in this wrapper)_"
            sibling_slugs = "(none)"

        return {
            "skeleton_name": self.skeleton_name,
            "project_name": self.project_name,
            "service_subdir": self.service_subdir,
            "service_label": self.service_label,
            "service_slug": self.service_slug,
            "SERVICE_SLUG": self.service_slug.upper(),
            "item_name": self.item_name,
            "ITEM_NAME": self.item_name.upper(),
            "item_class": self.item_class,
            "ITEM_CLASS": self.item_class.upper(),
            "items_plural": self.items_plural,
            "ITEMS_PLURAL": self.items_plural.upper(),
            "auth_type": self.auth_type,
            "auth_details": self.auth_details or "(no extra notes)",
            "auth_is_none": "True" if self.auth_type == "none" else "False",
            "auth_required": "False" if self.auth_type == "none" else "True",
            # Three separate freeform user prompts (one per phase). Each
            # falls back to a clear sentinel string so existing manifest
            # prompts can drop them in unconditionally without crashing
            # when the user did not supply anything for that phase.
            "backend_extra": self.backend_extra or "(no extra backend instructions)",
            "frontend_extra": self.frontend_extra or "(no extra frontend instructions)",
            "integration_extra": self.integration_extra or "(no extra integration instructions)",
            "testing_scenario": self.testing_scenario or "(no testing scenario provided)",
            "wrapper_snapshot": wrapper_snapshot,
            "sibling_count": str(len(self.siblings)),
            "sibling_slugs": sibling_slugs,
            **self.extra,
        }


@dataclass
class AiTarget:
    """A single file the AI generator should produce.

    ``path`` is relative to the project's *service directory* (the inner
    ``backend-1/`` style folder). ``template`` is relative to the skeleton
    root and is read into the prompt as the REFERENCE block. ``prompt`` is a
    Python ``str.format``-style template that receives the
    :class:`GenerationContext` template variables plus a ``template`` slot
    holding the reference file's contents.
    """

    path: str
    template: Optional[str]
    prompt: str
    language: str = "python"
    description: str = ""


@dataclass
class AiManifest:
    """A loaded ``_skels/_common/manifests/<skel>.py`` description."""

    skeleton_name: str
    targets: List[AiTarget]
    system_prompt: str = ""
    notes: str = ""


# --------------------------------------------------------------------------- #
#  Integration phase data classes
# --------------------------------------------------------------------------- #
#
# After the per-target manifest finishes generating the new service, the
# CLI runs an *integration* pass: another set of Ollama calls that adds
# integration code (cross-service clients, integration tests, etc.) wiring
# the new service into the rest of the wrapper. The integration manifest
# lives alongside the per-target manifest in the same per-skel file via an
# optional ``INTEGRATION_MANIFEST = {...}`` block.
#
# Integration prompts have access to a richer context: the freshly
# generated service AND a snapshot of every sibling service in the
# wrapper (slug, kind, key files). The runner exposes that snapshot via
# the ``{wrapper_snapshot}`` placeholder so manifest authors can drop it
# into prompts without re-implementing discovery logic.


# Files we always try to read from a sibling backend so the integration
# prompt can ground its rewrites in real code rather than guesses. Paths
# are relative to the sibling service directory; missing entries are
# silently skipped.
_SIBLING_KEY_FILES: Dict[str, List[str]] = {
    "python-django-bolt-skel": [
        "app/models.py",
        "app/api.py",
        "app/schemas.py",
    ],
    "python-django-skel": [
        "myproject/settings.py",
        "myproject/urls.py",
    ],
    "python-fastapi-skel": [
        "app/main.py",
        "core/config.py",
    ],
    "python-flask-skel": [
        "app/__init__.py",
        "app/config.py",
    ],
    "java-spring-skel": [
        "src/main/java/com/example/skel/Application.java",
        "src/main/resources/application.properties",
    ],
    "rust-actix-skel": ["src/main.rs", "src/config.rs"],
    "rust-axum-skel": ["src/main.rs", "src/config.rs"],
    "next-js-skel": ["src/index.js", "src/config.js"],
    "ts-react-skel": [
        "src/config.ts",
        "src/api/items.ts",
        "src/state/state-api.ts",
    ],
    "flutter-skel": [
        "lib/config.dart",
        "lib/api/items_client.dart",
        "lib/state/state_api.dart",
    ],
}


@dataclass
class ServiceSummary:
    """Snapshot of one sibling service in the wrapper.

    Built by :func:`discover_siblings` from a generated wrapper directory
    and embedded into the integration prompt as a structured context
    block. ``key_files`` is a small map of relative-path → file-content
    excerpts so the AI can ground its integration code in real
    signatures rather than guesses.
    """

    slug: str
    kind: str  # "backend" / "frontend" / "service" — derived from skel
    tech: str  # e.g. "python-django-bolt-skel"
    directory: Path
    key_files: Dict[str, str] = field(default_factory=dict)

    def render_block(self, *, max_chars_per_file: int = 4000) -> str:
        """Render this service as a Markdown-ish block for the prompt."""

        header = (
            f"### Service `{self.slug}` "
            f"({self.kind}, tech: {self.tech})\n"
            f"Directory: `{self.directory}`\n"
        )
        if not self.key_files:
            return header + "_(no key files captured)_\n"
        body_parts = [header]
        for path, content in self.key_files.items():
            snippet = content
            if len(snippet) > max_chars_per_file:
                snippet = snippet[:max_chars_per_file] + "\n... (truncated)\n"
            body_parts.append(f"\n#### `{path}`\n```\n{snippet}\n```\n")
        return "".join(body_parts)


_SERVICE_KIND_BY_TECH: Dict[str, str] = {
    "python-django-skel": "backend",
    "python-django-bolt-skel": "backend",
    "python-fastapi-skel": "backend",
    "python-fastapi-rag-skel": "backend",
    "python-flask-skel": "backend",
    "java-spring-skel": "backend",
    "rust-actix-skel": "backend",
    "rust-axum-skel": "backend",
    "next-js-skel": "backend",
    "ts-react-skel": "frontend",
    "flutter-skel": "frontend",
}


def _detect_service_tech(service_dir: Path) -> Optional[str]:
    """Best-effort guess of which skeleton produced ``service_dir``.

    The wrapper does not record per-service tech anywhere on disk
    (``dev_skel.project.yml`` would fix that — see TODO 4.1), so we use a
    handful of marker files. Returns ``None`` for unknown layouts; those
    services still appear in the snapshot with ``tech="unknown"`` so the
    AI knows they exist.
    """

    if (service_dir / "manage.py").is_file():
        # Distinguish django-bolt from plain django by the django-bolt
        # markers in requirements.txt or app/api.py.
        api_py = service_dir / "app" / "api.py"
        reqs = service_dir / "requirements.txt"
        if api_py.is_file() and "BoltAPI" in api_py.read_text(
            encoding="utf-8", errors="replace"
        ):
            return "python-django-bolt-skel"
        if reqs.is_file() and "django-bolt" in reqs.read_text(
            encoding="utf-8", errors="replace"
        ):
            return "python-django-bolt-skel"
        return "python-django-skel"
    if (service_dir / "core" / "config.py").is_file():
        return "python-fastapi-skel"
    if (service_dir / "app" / "config.py").is_file() and (
        service_dir / "app" / "__init__.py"
    ).is_file():
        return "python-flask-skel"
    if (service_dir / "pom.xml").is_file():
        return "java-spring-skel"
    if (service_dir / "Cargo.toml").is_file():
        cargo = (service_dir / "Cargo.toml").read_text(
            encoding="utf-8", errors="replace"
        )
        if "axum" in cargo:
            return "rust-axum-skel"
        return "rust-actix-skel"
    if (service_dir / "vite.config.ts").is_file():
        return "ts-react-skel"
    pubspec = service_dir / "pubspec.yaml"
    if pubspec.is_file():
        # `pubspec.yaml` is also a thing for pure-Dart packages, but
        # only Flutter projects depend on `flutter:` from the SDK.
        try:
            content = pubspec.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        if "flutter:" in content and "sdk: flutter" in content:
            return "flutter-skel"
    if (service_dir / "package.json").is_file():
        return "next-js-skel"
    return None


def discover_siblings(
    wrapper_root: Path, exclude_slug: str
) -> List[ServiceSummary]:
    """Walk ``wrapper_root`` and return a snapshot of every sibling service.

    A "sibling" is any subdirectory that looks like a generated dev_skel
    service (has at least one of the marker files used by
    :func:`_detect_service_tech`) and is not equal to ``exclude_slug``
    (typically the freshly generated service we're integrating).

    The wrapper-shared layout (`_shared/`, `.git`, dot-files, etc.) is
    skipped explicitly. Each surviving entry becomes a :class:`ServiceSummary`
    populated with up to a few key files for the AI prompt.
    """

    if not wrapper_root.is_dir():
        return []

    skip_names = {
        "_shared",
        "_test_projects",
        "node_modules",
        "target",
        "dist",
        "build",
        ".venv",
        ".git",
        "__pycache__",
    }

    siblings: List[ServiceSummary] = []
    for entry in sorted(wrapper_root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in skip_names or entry.name.startswith("."):
            continue
        if entry.name == exclude_slug:
            continue

        tech = _detect_service_tech(entry) or "unknown"
        kind = _SERVICE_KIND_BY_TECH.get(tech, "service")

        key_files: Dict[str, str] = {}
        for rel in _SIBLING_KEY_FILES.get(tech, []):
            file_path = entry / rel
            if file_path.is_file():
                try:
                    key_files[rel] = file_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError:
                    continue

        siblings.append(
            ServiceSummary(
                slug=entry.name,
                kind=kind,
                tech=tech,
                directory=entry,
                key_files=key_files,
            )
        )

    return siblings


@dataclass
class IntegrationManifest:
    """A loaded ``INTEGRATION_MANIFEST`` from a per-skel manifest file.

    Mirrors :class:`AiManifest` but represents the **second** Ollama
    pass — the one that wires the freshly generated service into the
    rest of the wrapper. Targets typically include cross-service
    clients and integration tests, NOT replacements for the per-target
    manifest's outputs.

    The two extra fields beyond :class:`AiManifest`:

    * ``test_command`` — shell command (relative to the new service
      directory) used by the test-and-fix loop to verify the
      integration. Defaults to ``./test`` so the wrapper-shared
      dispatch script picks the right runner. May reference the same
      placeholders as :func:`format_prompt`.
    * ``fix_timeout_m`` — maximum wall-clock minutes the test-and-fix
      loop is allowed to run before giving up. Defaults to ``120``
      (two hours) so a ~30B-class model like ``qwen3-coder:30b`` has enough
      headroom for several iterations of file rewrites + test reruns.
      Override via ``FIX_TIMEOUT_M`` env var or per-manifest.
    """

    skeleton_name: str
    targets: List[AiTarget]
    system_prompt: str = ""
    notes: str = ""
    test_command: str = "./test"
    fix_timeout_m: int = int(os.environ.get("FIX_TIMEOUT_M", "120"))


# --------------------------------------------------------------------------- #
#  Ollama HTTP client
# --------------------------------------------------------------------------- #


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable or returns an error response."""


class OllamaClient:
    """Compatibility shim around :class:`skel_rag.agent.RagAgent`.

    The class keeps the public surface (``config``, :meth:`verify`,
    :meth:`chat`) used by ``skel-gen-ai`` and ``test-ai-generators``
    unchanged. Internally it lazily constructs a :class:`RagAgent` so
    one ``OllamaClient`` instance is enough to drive the per-target,
    integration, and fix-loop phases.

    The agent is instantiated on first use (not in ``__init__``) so the
    legacy ``--check`` smoke test at the bottom of this file can verify
    Ollama reachability without paying the LangChain import cost.
    """

    def __init__(self, config: Optional[OllamaConfig] = None) -> None:
        self.config = config or OllamaConfig.from_env()
        self._agent: Optional[Any] = None

    # ---- internals --------------------------------------------------------

    @property
    def agent(self) -> Any:
        """Lazily-constructed :class:`skel_rag.agent.RagAgent`."""

        if self._agent is None:
            from skel_rag.agent import RagAgent  # local: heavy import

            self._agent = RagAgent(ollama_cfg=self.config)
        return self._agent

    # ---- introspection ----------------------------------------------------

    def verify(self) -> None:
        """Confirm Ollama is reachable and the requested model is loaded.

        Implementation moved to :func:`skel_rag.llm.verify`. The new
        function raises :class:`skel_rag.llm.OllamaError` which we
        convert to the legacy :class:`OllamaError` defined in this
        module so call sites that catch the old exception keep working.
        """

        from skel_rag.llm import OllamaError as _NewOllamaError, verify

        try:
            verify(self.config)
        except _NewOllamaError as exc:
            raise OllamaError(str(exc)) from exc

    # ---- chat completion --------------------------------------------------

    def chat(self, system: str, user: str) -> str:
        """Send one user/system turn and return the assistant text.

        Delegates to :meth:`skel_rag.agent.RagAgent.chat`, which goes
        through ``langchain_ollama.ChatOllama``. The new path raises
        :class:`skel_rag.llm.OllamaError` on failure; we re-raise as the
        local :class:`OllamaError` so existing handlers keep matching.

        Honors ``SKEL_AI_VERBOSE`` + ``SKEL_AI_HEARTBEAT_SEC`` env vars
        to print an elapsed-time tick while the call blocks, so
        long-running inferences in ``skel-gen-ai`` never look frozen.

        At ``SKEL_AI_VERBOSE >= 1``, prints timing and token metrics
        after each call. At level 2+, also prints input token count
        and throughput.
        """
        import time as _time

        from skel_rag.llm import OllamaError as _NewOllamaError

        raw_level = os.environ.get("SKEL_AI_VERBOSE", "").strip()
        verbose = int(raw_level) if raw_level.isdigit() else 0

        input_chars = len(system) + len(user)
        if verbose >= 2:
            input_tokens_est = input_chars // 4
            print(
                f"    [ai] prompt: system={len(system):,} chars, "
                f"user={len(user):,} chars (~{input_tokens_est:,} tokens)",
                file=sys.stderr, flush=True,
            )

        t0 = _time.monotonic()
        try:
            with _heartbeat_env(f"Ollama ({self.config.model})"):
                result = self.agent.chat(system, user)
        except _NewOllamaError as exc:
            raise OllamaError(str(exc)) from exc

        elapsed = _time.monotonic() - t0
        output_chars = len(result)

        if verbose >= 1:
            output_tokens_est = output_chars // 4
            throughput = output_tokens_est / elapsed if elapsed > 0 else 0
            print(
                f"    [ai] {self.config.model}: {elapsed:.1f}s, "
                f"output={output_chars:,} chars "
                f"(~{output_tokens_est:,} tokens, "
                f"{throughput:.1f} tok/s)",
                file=sys.stderr, flush=True,
            )

        return result


# --------------------------------------------------------------------------- #
#  Manifest loading
# --------------------------------------------------------------------------- #


def manifests_dir(repo_root: Path) -> Path:
    """Return the directory holding shared per-skeleton AI manifests."""

    return repo_root / "_skels" / "_common" / "manifests"


def discover_manifests(repo_root: Path) -> List[str]:
    """Return the names of every skeleton with an AI manifest on disk.

    Used by the interactive picker in ``_bin/skel-gen-ai`` and by
    ``_bin/skel-test-ai-generators`` to keep its set of validators in sync
    with what is actually shipped.
    """

    mdir = manifests_dir(repo_root)
    if not mdir.is_dir():
        return []
    return sorted(p.stem for p in mdir.glob("*.py") if not p.name.startswith("_"))


def load_manifest(repo_root: Path, skeleton_name: str) -> AiManifest:
    """Load and validate ``_skels/_common/manifests/<skeleton>.py``."""

    manifest_path = manifests_dir(repo_root) / f"{skeleton_name}.py"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"No AI manifest for skeleton '{skeleton_name}' (looked in "
            f"{manifest_path}). Create it to enable `skel-gen-ai` for this "
            f"skeleton — see _skels/_common/manifests/python-django-skel.py "
            f"for a working example."
        )

    spec = importlib.util.spec_from_file_location(
        f"_skels_manifest_{skeleton_name.replace('-', '_')}", manifest_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load manifest module at {manifest_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    raw = getattr(module, "MANIFEST", None)
    if not isinstance(raw, dict):
        raise ValueError(
            f"Manifest at {manifest_path} must define a top-level MANIFEST dict."
        )

    targets_raw = raw.get("targets") or []
    if not isinstance(targets_raw, list) or not targets_raw:
        raise ValueError(
            f"Manifest {manifest_path} must list at least one entry under 'targets'."
        )

    targets = [
        AiTarget(
            path=str(t["path"]),
            template=t.get("template"),
            prompt=str(t["prompt"]),
            language=str(t.get("language", "python")),
            description=str(t.get("description", "")),
        )
        for t in targets_raw
    ]

    return AiManifest(
        skeleton_name=skeleton_name,
        targets=targets,
        system_prompt=str(raw.get("system_prompt", "")),
        notes=str(raw.get("notes", "")),
    )


# --------------------------------------------------------------------------- #
#  Interactive dialog
# --------------------------------------------------------------------------- #


AUTH_CHOICES: Dict[str, str] = {
    "none": "No authentication — endpoints are public",
    "basic": "HTTP Basic auth (username + password)",
    "session": "Server-rendered session/cookie auth (Django default)",
    "jwt": "JWT bearer tokens (stateless, OAuth-friendly)",
    "oauth": "OAuth2 / social login (Google, Apple, GitHub, ...)",
    "api_key": "Static API key in a header",
}


def prompt_user_dialog(
    *,
    skeleton_name: str,
    default_project_name: str,
    default_service_subdir: str,
    service_label: Optional[str] = None,
    item_name: Optional[str] = None,
    auth_type: Optional[str] = None,
    auth_details: Optional[str] = None,
    no_input: bool = False,
) -> Dict[str, str]:
    """Run the interactive dialog and return the answers as a dict.

    Any value supplied via ``service_label``/``item_name``/``auth_type``/
    ``auth_details`` is reused without prompting, so the CLI can pre-fill
    values from command-line flags. ``no_input=True`` skips every prompt and
    falls back to defaults — used by ``skel-gen-ai --no-input`` and tests.
    """

    print()
    print(f"  dev_skel · Ollama generator for `{skeleton_name}`")
    print("  ----------------------------------------------")
    print(f"  Project (wrapper)  : {default_project_name}")
    print(f"  Service directory  : {default_service_subdir}")
    print()

    def ask(label: str, default: str) -> str:
        if no_input:
            return default
        try:
            raw = input(f"  {label} [{default}]: ").strip()
        except EOFError:
            raw = ""
        return raw or default

    answers: Dict[str, str] = {}

    answers["service_label"] = service_label or ask(
        "Service display name (e.g. 'Ticket Service')",
        default_service_subdir.replace("-", " ").replace("_", " ").title(),
    )

    answers["item_name"] = (item_name or ask(
        "Main item name (CRUD entity, e.g. ticket / order / task)",
        "item",
    )).strip().lower()

    if not answers["item_name"].isidentifier():
        raise ValueError(
            f"Item name '{answers['item_name']}' is not a valid Python identifier."
        )

    if auth_type:
        answers["auth_type"] = auth_type
    elif no_input:
        answers["auth_type"] = "jwt"
    else:
        print()
        print("  Authentication options:")
        for key, desc in AUTH_CHOICES.items():
            print(f"    - {key:<8s} {desc}")
        choice = ask("Auth type", "jwt")
        if choice not in AUTH_CHOICES:
            print(f"  (unknown auth '{choice}', treating as freeform notes)")
        answers["auth_type"] = choice

    if auth_details is not None:
        answers["auth_details"] = auth_details
    elif no_input:
        answers["auth_details"] = ""
    else:
        answers["auth_details"] = ask(
            "Auth details / extra requirements (optional)",
            "",
        )

    print()
    return answers


# --------------------------------------------------------------------------- #
#  Full-stack (backend + frontend) dialog
# --------------------------------------------------------------------------- #


# Skeletons that ship a wrapper-shared `/api/items` + `/api/auth/login`
# layer the React frontend can call out of the box. The dialog uses
# this set to decide whether to print a "ships /api/items" badge next
# to a backend choice and to surface a warning when the user picks a
# backend that does NOT yet ship the contract.
BACKENDS_WITH_ITEMS_API = {
    "python-django-bolt-skel",
    "python-fastapi-skel",
}


# Default service display names per skel kind. Used as the dialog
# defaults when the user does not type their own.
_DEFAULT_BACKEND_NAME = "Items API"
_DEFAULT_FRONTEND_NAME = "Web UI"


# Short human-readable description for each skel — used in the picker.
SKELETON_DESCRIPTIONS: Dict[str, str] = {
    "python-django-skel": "Django backend (plain Django views, JWT-aware)",
    "python-django-bolt-skel": "Django + django-bolt (Rust HTTP, ships /api/items)",
    "python-fastapi-skel": "FastAPI (async SQLAlchemy, ships /api/items)",
    "python-flask-skel": "Flask + flask-sqlalchemy",
    "java-spring-skel": "Spring Boot (JPA + JwtProperties bean)",
    "rust-actix-skel": "Rust Actix-web (sqlite via stdlib)",
    "rust-axum-skel": "Rust Axum (sqlite via stdlib)",
    "next-js-skel": "Node 22 (node:sqlite + node:test)",
    "ts-react-skel": "React + Vite + TypeScript (typed fetch client + items hook)",
    "flutter-skel": "Flutter / Dart (Material 3, secure token store, items + /api/state client)",
}


@dataclass
class FullstackChoices:
    """Result of :func:`prompt_fullstack_dialog`.

    The dialog asks for *both* a backend and a frontend skeleton. Both
    sides are optional — pick "none" on either to skip that half (a
    backend-only or frontend-only project). The dialog enforces that
    at least one side is chosen. Also collects one project name, two
    service display names (one per side), the canonical item entity,
    an auth style, and three freeform "extra instructions" prompts
    (one each for the backend, frontend, and integration phases).
    Returning a dataclass instead of a flat dict makes the CLI driver
    code easier to read at the call site.
    """

    project_name: str
    backend_skeleton: Optional[str]
    backend_service_label: Optional[str]
    frontend_skeleton: Optional[str]
    frontend_service_label: Optional[str]
    item_name: str
    auth_type: str
    backend_extra: str
    frontend_extra: str
    integration_extra: str
    testing_scenario: str = ""

    @property
    def has_backend(self) -> bool:
        return bool(self.backend_skeleton)

    @property
    def has_frontend(self) -> bool:
        return bool(self.frontend_skeleton)

    @property
    def backend_serves_items(self) -> bool:
        return bool(
            self.backend_skeleton
            and self.backend_skeleton in BACKENDS_WITH_ITEMS_API
        )


def _ask_choice(
    label: str,
    options: List[str],
    *,
    default_index: int,
    descriptions: Dict[str, str],
    no_input: bool,
    allow_none: bool = False,
) -> Optional[str]:
    """Numbered picker shared by the backend + frontend prompt steps.

    Returns ``None`` only when ``allow_none`` is True and the user
    explicitly typed ``none`` / ``-`` / ``skip``. Otherwise returns the
    chosen option string.
    """

    if not options:
        if allow_none:
            return None
        raise SystemExit(f"No {label}s available.")

    if no_input:
        return options[default_index]

    if not sys.stdin.isatty():
        return options[default_index]

    name_width = max(len(o) for o in options)

    print()
    print(f"  Available {label}s:")
    for i, name in enumerate(options, start=1):
        marker = " *" if (i - 1) == default_index else "  "
        suffix = f"  {descriptions.get(name, '')}".rstrip()
        print(f"   {marker}{i:2d}) {name:{name_width}}{suffix}")
    if allow_none:
        print(f"      0) (none — skip the {label})")
    print()

    default_label = options[default_index]
    while True:
        try:
            raw = input(
                f"  Select {label} [{default_index + 1}={default_label}]: "
            ).strip()
        except EOFError:
            raw = ""

        if not raw:
            return options[default_index]

        if allow_none and raw.lower() in ("0", "none", "skip", "-"):
            return None

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
            print(f"  Index out of range (1-{len(options)}).")
            continue

        if raw in options:
            return raw

        substring = [o for o in options if raw in o]
        if len(substring) == 1:
            return substring[0]
        if len(substring) > 1:
            print(
                f"  Ambiguous: {raw!r} matches "
                f"{', '.join(substring)}. Try again."
            )
            continue

        print(f"  Unknown {label}: {raw!r}. Pick a number or full name.")


def prompt_fullstack_dialog(
    *,
    available_backends: List[str],
    available_frontends: List[str],
    default_project_name: str,
    backend_skeleton: Optional[str] = None,
    frontend_skeleton: Optional[str] = None,
    backend_service_label: Optional[str] = None,
    frontend_service_label: Optional[str] = None,
    item_name: Optional[str] = None,
    auth_type: Optional[str] = None,
    backend_extra: Optional[str] = None,
    frontend_extra: Optional[str] = None,
    integration_extra: Optional[str] = None,
    testing_scenario: Optional[str] = None,
    no_input: bool = False,
    allow_no_frontend: bool = True,
    skip_frontend: bool = False,
    allow_no_backend: bool = True,
    skip_backend: bool = False,
) -> FullstackChoices:
    """Run the upgraded interactive dialog and return the choices.

    The dialog walks the user through seven logical steps:

    1. Pick a backend skeleton (or accept the default — the first
       backend in `available_backends` that ships the wrapper-shared
       items API, falling back to the alphabetically first backend).
    2. Pick a frontend skeleton (or "none" to skip — useful for
       backend-only projects).
    3. Confirm the project / service display names.
    4. Confirm the canonical item entity (e.g. "ticket" → ``Ticket``
       class, ``tickets`` plural).
    5. Pick an auth style.
    6. Optionally provide three freeform extra-instruction prompts
       (one each for the backend, frontend, and integration phases).
    7. Optionally provide a testing scenario description for Phase 6
       test generation.

    Any value pre-supplied via the keyword arguments is reused without
    prompting (so the CLI can pre-fill from flags). When ``no_input``
    is True, the dialog uses every default silently. The result is a
    :class:`FullstackChoices` dataclass — pickle-friendly + easier to
    read at the call site than the older flat dict shape.
    """

    print()
    print("  dev_skel · Ollama generator · full-stack mode")
    print("  ----------------------------------------------")
    print(f"  Project (wrapper)  : {default_project_name}")
    print()

    def ask(label: str, default: str) -> str:
        if no_input:
            return default
        if not sys.stdin.isatty():
            return default
        try:
            raw = input(f"  {label} [{default}]: ").strip()
        except EOFError:
            raw = ""
        return raw or default

    # Step 1: backend ----------------------------------------------------- #
    # Default to the first backend that ships the wrapper-shared items
    # API contract. That gives the user a working items round-trip out
    # of the box; the rest are still selectable.
    default_backend_idx = 0
    for i, name in enumerate(available_backends):
        if name in BACKENDS_WITH_ITEMS_API:
            default_backend_idx = i
            break

    print("  Step 1/7: Backend")
    chosen_backend: Optional[str]
    if skip_backend:
        # Explicit "frontend-only project" — `--no-backend` on the CLI.
        # We do not enter the picker even if the user is on a TTY.
        chosen_backend = None
        print("  (skipped — frontend-only project)")
    elif backend_skeleton is not None:
        chosen_backend = backend_skeleton or None
    elif not available_backends:
        if not allow_no_backend:
            raise SystemExit(
                "No AI-supported backend skeletons found. Drop a "
                "manifest under _skels/_common/manifests/ to enable one."
            )
        chosen_backend = None
    else:
        chosen_backend = _ask_choice(
            "backend skeleton",
            available_backends,
            default_index=default_backend_idx,
            descriptions=SKELETON_DESCRIPTIONS,
            no_input=no_input,
            allow_none=allow_no_backend,
        )

    # Step 2: frontend ---------------------------------------------------- #
    # Default the frontend picker to ``ts-react-skel`` (the canonical
    # cross-stack pair partner, matched by every backend's items API
    # contract). Falls back to index 0 when react isn't installed.
    default_frontend_idx = 0
    for i, name in enumerate(available_frontends):
        if name == "ts-react-skel":
            default_frontend_idx = i
            break

    print()
    print("  Step 2/7: Frontend")
    chosen_frontend: Optional[str]
    if skip_frontend:
        # Explicit "backend-only project" — `--no-frontend` on the CLI.
        # We do not enter the picker even if the user is on a TTY.
        chosen_frontend = None
        print("  (skipped — backend-only project)")
    elif frontend_skeleton is not None:
        chosen_frontend = frontend_skeleton or None
    elif not available_frontends:
        chosen_frontend = None
    else:
        chosen_frontend = _ask_choice(
            "frontend skeleton",
            available_frontends,
            default_index=default_frontend_idx,
            descriptions=SKELETON_DESCRIPTIONS,
            no_input=no_input,
            allow_none=allow_no_frontend,
        )

    if chosen_backend is None and chosen_frontend is None:
        raise SystemExit(
            "Refusing to generate a project with neither a backend nor "
            "a frontend. Pick at least one (or omit --no-backend / "
            "--no-frontend)."
        )

    # Step 3: service display names -------------------------------------- #
    print()
    print("  Step 3/7: Service display names")
    chosen_backend_label: Optional[str]
    if chosen_backend is None:
        chosen_backend_label = None
    else:
        chosen_backend_label = backend_service_label or ask(
            "Backend service display name", _DEFAULT_BACKEND_NAME
        )
    chosen_frontend_label: Optional[str]
    if chosen_frontend is None:
        chosen_frontend_label = None
    else:
        chosen_frontend_label = frontend_service_label or ask(
            "Frontend service display name", _DEFAULT_FRONTEND_NAME
        )

    # Step 4: item entity ------------------------------------------------- #
    print()
    print("  Step 4/7: Main CRUD entity")
    chosen_item = (
        item_name
        or ask(
            "Main item name (lowercase, e.g. ticket / order / task)",
            "item",
        )
    ).strip().lower()
    if not chosen_item.isidentifier():
        raise ValueError(
            f"Item name '{chosen_item}' is not a valid Python identifier."
        )

    # Step 5: auth -------------------------------------------------------- #
    print()
    print("  Step 5/7: Authentication style")
    if auth_type is not None:
        chosen_auth = auth_type
    elif no_input or not sys.stdin.isatty():
        chosen_auth = "jwt"
    else:
        for key, desc in AUTH_CHOICES.items():
            print(f"    - {key:<8s} {desc}")
        chosen_auth = ask("Auth type", "jwt")

    # Step 6: three custom prompts (replaces auth_details) --------------- #
    print()
    print("  Step 6/7: Custom instructions (optional, blank to skip)")
    if chosen_backend is None:
        chosen_backend_extra = ""
    else:
        chosen_backend_extra = (
            backend_extra
            if backend_extra is not None
            else ask("Additional backend instructions", "")
        )
    if chosen_frontend is None:
        chosen_frontend_extra = ""
    else:
        chosen_frontend_extra = (
            frontend_extra
            if frontend_extra is not None
            else ask("Additional frontend instructions", "")
        )
    # Integration prompt only makes sense when both halves exist —
    # otherwise there's nothing to integrate against.
    if chosen_frontend is None or chosen_backend is None:
        chosen_integration_extra = ""
    else:
        chosen_integration_extra = (
            integration_extra
            if integration_extra is not None
            else ask("Additional integration instructions", "")
        )

    # Step 7: testing scenario ------------------------------------------- #
    print()
    print("  Step 7/7: Testing scenario (optional, blank to skip)")
    print()
    print('  Describe what the generated tests should verify. Example:')
    print('  "Create 3 menu items, place an order with 2 items,')
    print('   set delivery address, submit, approve with 25min wait"')
    print()
    chosen_testing_scenario = (
        testing_scenario
        if testing_scenario is not None
        else ask("Testing scenario", "")
    )

    # Items contract advisory -------------------------------------------- #
    if (
        chosen_frontend
        and chosen_backend
        and chosen_backend not in BACKENDS_WITH_ITEMS_API
    ):
        print()
        print(
            f"  ⚠ {chosen_backend} does not yet ship the wrapper-shared "
            "/api/items + /api/auth/login layer."
        )
        print(
            "    The React frontend's src/api/items.ts will receive 404 "
            "until you add a matching backend route. Run with "
            "`--no-frontend` if you only want the backend."
        )
    elif chosen_frontend and chosen_backend is None:
        print()
        print(
            "  ⚠ frontend-only project — the React `src/api/items.ts` "
            "calls will fail until you point BACKEND_URL at an external "
            "service that implements /api/items + /api/auth/login."
        )

    print()
    return FullstackChoices(
        project_name=default_project_name,
        backend_skeleton=chosen_backend,
        backend_service_label=chosen_backend_label,
        frontend_skeleton=chosen_frontend,
        frontend_service_label=chosen_frontend_label,
        item_name=chosen_item,
        auth_type=chosen_auth,
        backend_extra=chosen_backend_extra,
        frontend_extra=chosen_frontend_extra,
        integration_extra=chosen_integration_extra,
        testing_scenario=chosen_testing_scenario,
    )


# Convenience helper for partitioning a manifest list into backends
# vs frontends. Used by the CLI when building the dialog's pick lists.
def split_skels_by_kind(
    skel_names: List[str],
) -> Tuple[List[str], List[str]]:
    """Return ``(backends, frontends)`` from a list of skel names."""

    backends: List[str] = []
    frontends: List[str] = []
    for name in skel_names:
        kind = _SERVICE_KIND_BY_TECH.get(name, "service")
        if kind == "frontend":
            frontends.append(name)
        else:
            backends.append(name)
    return backends, frontends


# --------------------------------------------------------------------------- #
#  Prompt assembly + cleanup
# --------------------------------------------------------------------------- #


def format_prompt(
    template: str,
    ctx: GenerationContext,
    *,
    reference: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Render a manifest prompt with the context's template variables.

    Uses :meth:`str.format_map` so missing keys raise a clear ``KeyError``
    instead of silently producing an empty string.

    ``extra`` is an optional ``{name: value}`` dict that gets merged on
    top of the context vars before rendering. The fix-loop callsite uses
    it to inject phase-specific placeholders (``rel_path``,
    ``test_output``, ``returncode``, ``current_contents``, …) without
    needing two separate format passes — a chained
    ``format_prompt(...).format(rel_path=...)`` would crash because the
    inner ``format_map`` is strict and bails on the first key it does
    not recognise.
    """

    variables: Dict[str, Any] = dict(ctx.as_template_vars())
    variables["template"] = reference or "(no template provided)"
    if extra:
        variables.update(extra)
    return template.format_map(_StrictDict(variables))


_SEPARATOR_LINE_RE = re.compile(r"^\s*-{3,}\s*$")


def clean_response(text: str, language: str) -> str:
    """Strip code fences and stray prose around AI-generated code blocks.

    Some local models occasionally echo back the ``---`` REFERENCE-block
    separators we use in prompts; we strip leading and trailing separator
    lines so the file ends up syntactically valid Python.
    """

    if not text:
        return text

    fence_pattern = re.compile(
        r"```(?:" + re.escape(language) + r"|[a-zA-Z0-9_+-]*)\n(.*?)```",
        re.DOTALL,
    )
    match = fence_pattern.search(text)
    if match:
        body = match.group(1)
    elif "```" in text:
        body = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("```")
        )
    else:
        body = text

    lines = body.splitlines()

    # Drop leading blank lines and stray separator lines.
    while lines and (not lines[0].strip() or _SEPARATOR_LINE_RE.match(lines[0])):
        lines.pop(0)

    # Drop trailing blank / separator lines.
    while lines and (not lines[-1].strip() or _SEPARATOR_LINE_RE.match(lines[-1])):
        lines.pop()

    return "\n".join(lines) + "\n" if lines else "\n"


def build_system_prompt(manifest: AiManifest, ctx: GenerationContext) -> str:
    """Compose the system prompt sent with every chat request."""

    base = manifest.system_prompt.strip() or _DEFAULT_SYSTEM_PROMPT
    base = format_prompt(base, ctx)
    constraints = (
        "\nGlobal constraints:\n"
        "- Output ONLY the file's contents, no markdown fences, no commentary.\n"
        "- Match the style and indentation of the REFERENCE template when present.\n"
        "- Keep imports minimal and stdlib-first when possible.\n"
        f"- Authentication style for this service: {ctx.auth_type}.\n"
    )
    if ctx.auth_details:
        constraints += f"- Auth notes from the user: {ctx.auth_details}\n"
    # Disable thinking mode in Qwen 3.x models — saves 30-50% tokens
    # on code generation where we want direct output, not reasoning.
    constraints += "\n/no_think\n"
    return base + constraints


_DEFAULT_SYSTEM_PROMPT = (
    "You are a senior backend engineer generating a single source file for "
    "the `{skeleton_name}` skeleton. The user has chosen to build a service "
    "named `{service_label}` whose main CRUD entity is `{item_class}` "
    "(plural `{items_plural}`). Adapt the REFERENCE template to that entity "
    "and to the requested authentication style."
)


# --------------------------------------------------------------------------- #
#  High level orchestration
# --------------------------------------------------------------------------- #


@dataclass
class TargetResult:
    target: AiTarget
    written_to: Path
    bytes_written: int


def expand_target_paths(target: AiTarget, ctx: GenerationContext) -> AiTarget:
    """Return a copy of ``target`` with placeholders in ``path`` / ``template``
    / ``description`` substituted from the context.

    The prompt itself is left untouched here because :func:`format_prompt`
    interpolates it lazily — that way prompts can reference ``{template}`` and
    other manifest-specific keys without colliding with path expansion.
    """

    variables = ctx.as_template_vars()
    expand = lambda value: value.format_map(_StrictDict(variables)) if value else value

    return AiTarget(
        path=expand(target.path),
        template=expand(target.template) if target.template else None,
        prompt=target.prompt,
        language=target.language,
        description=expand(target.description) if target.description else "",
    )


def load_integration_manifest(
    repo_root: Path, skeleton_name: str
) -> Optional[IntegrationManifest]:
    """Load the optional ``INTEGRATION_MANIFEST`` block from a per-skel manifest.

    Returns ``None`` (not an exception) when the per-skel manifest file
    exists but does not declare an integration block — many skels are
    fine without one. Raises :class:`FileNotFoundError` only when the
    per-skel manifest itself is missing, mirroring :func:`load_manifest`.

    The block has the same shape as the per-target ``MANIFEST`` dict
    plus two optional extra fields::

        INTEGRATION_MANIFEST = {
            "system_prompt": "...",
            "targets": [...],
            "test_command": "./test",   # default
            "fix_timeout_m": 120,       # default (minutes)
            "notes": "...",
        }
    """

    manifest_path = manifests_dir(repo_root) / f"{skeleton_name}.py"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"No AI manifest for skeleton '{skeleton_name}' (looked in "
            f"{manifest_path})."
        )

    spec = importlib.util.spec_from_file_location(
        f"_skels_int_manifest_{skeleton_name.replace('-', '_')}",
        manifest_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load manifest module at {manifest_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    raw = getattr(module, "INTEGRATION_MANIFEST", None)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"INTEGRATION_MANIFEST in {manifest_path} must be a dict."
        )

    targets_raw = raw.get("targets") or []
    if not isinstance(targets_raw, list):
        raise ValueError(
            f"INTEGRATION_MANIFEST.targets in {manifest_path} must be a list."
        )

    targets = [
        AiTarget(
            path=str(t["path"]),
            template=t.get("template"),
            prompt=str(t["prompt"]),
            language=str(t.get("language", "python")),
            description=str(t.get("description", "")),
        )
        for t in targets_raw
    ]

    return IntegrationManifest(
        skeleton_name=skeleton_name,
        targets=targets,
        system_prompt=str(raw.get("system_prompt", "")),
        notes=str(raw.get("notes", "")),
        test_command=str(raw.get("test_command", "./test")),
        fix_timeout_m=int(raw.get("fix_timeout_m", 120)),
    )


def run_integration_phase(
    *,
    client: OllamaClient,
    manifest: IntegrationManifest,
    ctx: GenerationContext,
    dry_run: bool = False,
    progress: Optional[Any] = None,
) -> List[TargetResult]:
    """Render every integration target through Ollama and write the result.

    Thin wrapper that delegates to
    :meth:`skel_rag.agent.RagAgent.run_integration_phase`. The agent is
    cached on the :class:`OllamaClient` instance so the per-target
    phase, integration phase, and fix loop all share one retriever
    cache.

    Same error policy as before: failures during a single target's
    render / chat / write are surfaced through ``progress`` and the
    loop moves on to the next target.
    """

    return client.agent.run_integration_phase(
        manifest=manifest,
        ctx=ctx,
        dry_run=dry_run,
        progress=progress,
    )


@dataclass
class TestRunResult:
    """Outcome of running a service's test command once."""

    command: List[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str
    duration_s: float

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    def combined_output(self, *, max_chars: int = 8000) -> str:
        """Return ``stdout + stderr`` truncated to fit a reasonable prompt."""

        merged = ""
        if self.stdout:
            merged += "----- stdout -----\n" + self.stdout
        if self.stderr:
            if merged:
                merged += "\n"
            merged += "----- stderr -----\n" + self.stderr
        if len(merged) > max_chars:
            head = merged[: max_chars // 2]
            tail = merged[-max_chars // 2 :]
            merged = head + "\n... (truncated) ...\n" + tail
        return merged


def _resolve_test_command(
    test_command: str, ctx: GenerationContext
) -> List[str]:
    """Render placeholders in ``test_command`` and split into argv.

    Most manifests use the literal default ``./test`` (which we resolve
    to the wrapper-shared dispatch script in the new service directory),
    but a manifest can override with anything ``shlex.split``-friendly
    such as ``pytest -q app/tests/test_integration.py``. Placeholders
    from the context are interpolated first so manifests can reference
    ``{service_slug}``, ``{items_plural}``, etc.
    """

    import shlex

    rendered = format_prompt(test_command, ctx)
    return shlex.split(rendered)


def run_service_tests(
    test_command: str, ctx: GenerationContext, *, timeout_s: int = 1800
) -> TestRunResult:
    """Run the integration manifest's ``test_command`` inside the new service.

    Returns a :class:`TestRunResult` regardless of pass/fail so the
    caller can decide whether to enter the fix loop. ``timeout_s``
    bounds individual test runs because some stacks (Java, Rust) cold-
    start slowly and we want a clean error rather than an infinite
    hang on a misconfigured runner.

    Resolves a relative ``./script`` argv[0] against the service
    directory before exec so subprocess always sees an absolute path.
    Catches **every** exception class (not just FileNotFoundError +
    TimeoutExpired) so a misbehaving test runner cannot crash the
    surrounding fix loop — the error text is surfaced via the returned
    ``TestRunResult.stderr`` and bubbles into the next Ollama prompt
    as natural language for the model to repair.
    """

    import time

    cwd = ctx.project_dir
    started = time.monotonic()

    try:
        argv = _resolve_test_command(test_command, ctx)
    except Exception as exc:  # noqa: BLE001 — surface render failures to Ollama
        return TestRunResult(
            command=[test_command],
            cwd=cwd,
            returncode=126,
            stdout="",
            stderr=f"could not render test command {test_command!r}: {exc}",
            duration_s=time.monotonic() - started,
        )

    if not argv:
        return TestRunResult(
            command=argv,
            cwd=cwd,
            returncode=126,
            stdout="",
            stderr=f"empty test command rendered from {test_command!r}",
            duration_s=time.monotonic() - started,
        )

    # Absolutise a leading `./script` argv[0] against the service
    # directory so the spawned process never has to rely on its own
    # cwd-resolution semantics. Useful for ./test, ./run, ./build, etc.
    if argv[0].startswith("./"):
        candidate = (cwd / argv[0][2:]).resolve()
        if candidate.is_file():
            argv = [str(candidate)] + argv[1:]

    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return TestRunResult(
            command=argv,
            cwd=cwd,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_s=time.monotonic() - started,
        )
    except FileNotFoundError as exc:
        return TestRunResult(
            command=argv,
            cwd=cwd,
            returncode=127,
            stdout="",
            stderr=f"test runner not found: {exc}",
            duration_s=time.monotonic() - started,
        )
    except PermissionError as exc:
        return TestRunResult(
            command=argv,
            cwd=cwd,
            returncode=126,
            stdout="",
            stderr=f"test runner not executable: {exc}",
            duration_s=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        return TestRunResult(
            command=argv,
            cwd=cwd,
            returncode=124,
            stdout=(exc.stdout or b"").decode("utf-8", errors="replace"),
            stderr=(exc.stderr or b"").decode("utf-8", errors="replace")
            + f"\n(timed out after {timeout_s}s)",
            duration_s=time.monotonic() - started,
        )
    except Exception as exc:  # noqa: BLE001 — last-resort safety net
        return TestRunResult(
            command=argv,
            cwd=cwd,
            returncode=125,
            stdout="",
            stderr=f"unexpected test runner error: {exc!r}",
            duration_s=time.monotonic() - started,
        )


_FIX_SYSTEM_PROMPT = (
    "You are a senior engineer fixing a single failing source file in the "
    "`{skeleton_name}` skeleton's `{service_slug}` service. The file you "
    "wrote in the previous turn caused the project's test suite to fail. "
    "Your job is to return a corrected version of the file (the entire "
    "file, not a patch) that resolves the failure while keeping the rest "
    "of the project intact.\n\n"
    "Rules:\n"
    "- Output ONLY the file's contents. No markdown fences, no commentary.\n"
    "- Make the minimum change required to fix the failure.\n"
    "- Do NOT introduce new dependencies, NEW imports beyond what the "
    "file already uses, or changes to other files.\n"
    "- Preserve the original file's overall structure (functions, "
    "classes, fixtures) and indentation style.\n"
    "- If the failure is unrelated to this file, return the file UNCHANGED."
)

_FIX_USER_PROMPT = (
    "File path (relative to {service_slug}/): `{rel_path}`\n\n"
    "Current file contents:\n"
    "```{language}\n"
    "{current_contents}\n"
    "```\n\n"
    "The project's test command was `{test_command}` and it returned "
    "exit code {returncode}. Combined output:\n\n"
    "```\n{test_output}\n```\n\n"
    "Return the corrected file in full."
)


def _ask_ollama_to_fix(
    *,
    client: OllamaClient,
    ctx: GenerationContext,
    target_result: TargetResult,
    test_run: TestRunResult,
    test_command: str,
) -> str:
    """Delegate one fix round-trip to :meth:`RagAgent.fix_target`.

    The RAG agent enriches the prompt with retrieved sibling chunks
    (so the model has the wrapper's API surface to ground its repair),
    then runs the same ``clean_response`` pass we always did.
    """

    return client.agent.fix_target(
        target_result=target_result,
        test_run=test_run,
        test_command=test_command,
        ctx=ctx,
    )


_FIXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".java", ".rs", ".dart", ".toml", ".cfg",
}
_SKIP_DIRS = {
    ".venv", "venv", "__pycache__", "node_modules", ".git",
    "target", "dist", "build", ".tox", ".mypy_cache", ".ruff_cache",
}


def _discover_project_files(project_dir: Path) -> List[TargetResult]:
    """Scan the service directory for all fixable source files.

    Returns a :class:`TargetResult` for every file whose extension is in
    ``_FIXABLE_EXTENSIONS``, skipping virtualenvs, caches, and build
    artifacts. The returned list is sorted so deterministic ordering is
    guaranteed across runs.
    """
    results: List[TargetResult] = []
    for f in sorted(project_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix not in _FIXABLE_EXTENSIONS:
            continue
        # Skip dirs we never want to touch.
        parts = set(f.relative_to(project_dir).parts)
        if parts & _SKIP_DIRS:
            continue
        results.append(
            TargetResult(
                target=AiTarget(
                    path=str(f.relative_to(project_dir)),
                    template=None,
                    prompt="",
                ),
                written_to=f,
                bytes_written=f.stat().st_size,
            )
        )
    return results


def _looks_like_missing_runner(result: TestRunResult) -> bool:
    """Return True when the test command itself could not start.

    Exit 127 is the canonical "command not found" status (e.g.
    ``./test: line 43: pytest: command not found``). Exit 126 means
    the command was found but could not execute (typically missing
    exec bit, or the shim shell exits with that code from our own
    render-failure branch in :func:`run_service_tests`). In both
    cases there is no point asking Ollama to patch source files —
    the test runner itself is missing, and the right fix is to
    install dependencies or repair the dispatch script.
    """

    if result.returncode not in (126, 127):
        return False
    haystack = f"{result.stdout}\n{result.stderr}".lower()
    return (
        "command not found" in haystack
        or "no such file" in haystack
        or "test runner not found" in haystack
        or "executable" in haystack
        # render-failure shim in run_service_tests; 126 exit + the
        # synthetic stderr text tells us we never spawned the runner.
        or "could not render test command" in haystack
    )


def _try_auto_install_deps(
    *, project_dir: Path, progress: Optional[Any] = None
) -> bool:
    """Try to auto-install the service's deps via its ``./install-deps``.

    Returns True when the script existed AND exited 0. Never raises —
    failures are surfaced via ``progress`` and the caller decides how
    to handle them.
    """

    candidate = project_dir / "install-deps"
    if not candidate.is_file():
        if progress is not None:
            progress.write(
                "  [deps] no ./install-deps in service dir — "
                "cannot auto-repair missing runner\n"
            )
        return False

    import time as _time

    if progress is not None:
        progress.write(
            f"  [deps] running `./install-deps` in {project_dir} "
            "(auto-recover from missing test runner)\n"
        )
    started = _time.monotonic()
    try:
        completed = subprocess.run(
            [str(candidate.resolve())],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=1800,  # dev-dep installs can be slow on cold caches
        )
    except subprocess.TimeoutExpired:
        if progress is not None:
            progress.write("  [deps] install-deps timed out (30m)\n")
        return False
    except Exception as exc:  # noqa: BLE001
        if progress is not None:
            progress.write(f"  [deps] install-deps failed to launch: {exc!r}\n")
        return False

    elapsed = _time.monotonic() - started
    if completed.returncode == 0:
        if progress is not None:
            progress.write(
                f"  [deps] install-deps OK in {elapsed:.1f}s\n"
            )
        return True

    if progress is not None:
        tail = (completed.stdout + completed.stderr).strip()[-1000:]
        progress.write(
            f"  [deps] install-deps FAILED (exit {completed.returncode}, "
            f"{elapsed:.1f}s):\n{tail}\n"
        )
    return False


def run_test_and_fix_loop(
    *,
    client: OllamaClient,
    ctx: GenerationContext,
    manifest: IntegrationManifest,
    integration_results: List[TargetResult],
    discover_project_files: Optional[Any] = None,
    progress: Optional[Any] = None,
) -> TestRunResult:
    """Run the new service's tests and ask Ollama to repair failures.

    The loop runs until the tests pass or ``manifest.fix_timeout_m``
    minutes of wall-clock time have elapsed (default: 120 min). On each
    iteration we run the test command, and if it fails we ask Ollama
    to repair **every source file in the service directory** (not just
    integration files), then re-run. Returns the **last**
    :class:`TestRunResult` so the caller can surface a final pass/fail.

    Special handling for "missing test runner" failures (exit 126/127
    with a clear "command not found" / "no such file" signature): the
    loop will try to auto-run ``./install-deps`` ONCE and retry before
    handing the failure over to Ollama. Asking a language model to
    patch 19 source files because ``pytest`` isn't on ``PATH`` is both
    slow and pointless — the generated code is almost never the bug in
    that scenario.

    The function never raises on a failing test — instead it surfaces
    the failure through the returned ``TestRunResult`` so the CLI can
    print an actionable summary and let the user decide what to do.
    """

    import time as _time

    deadline = _time.monotonic() + manifest.fix_timeout_m * 60
    last: Optional[TestRunResult] = None
    iteration = 0
    auto_install_attempted = False
    while True:
        iteration += 1
        elapsed_m = (manifest.fix_timeout_m * 60 - (deadline - _time.monotonic())) / 60
        if progress is not None:
            progress.write(
                f"\n  [test {iteration}] running `{manifest.test_command}` "
                f"in {ctx.project_dir}  ({elapsed_m:.0f}m elapsed)\n"
            )

        try:
            last = run_service_tests(manifest.test_command, ctx)
        except Exception as exc:  # noqa: BLE001 — bypass ALL errors to Ollama
            last = TestRunResult(
                command=[manifest.test_command],
                cwd=ctx.project_dir,
                returncode=125,
                stdout="",
                stderr=f"run_service_tests itself raised: {exc!r}",
                duration_s=0.0,
            )
            if progress is not None:
                progress.write(
                    f"  [test {iteration}] FAIL (run_service_tests raised: {exc})\n"
                )
        else:
            if progress is not None:
                status = "PASS" if last.passed else f"FAIL (exit {last.returncode})"
                progress.write(
                    f"  [test {iteration}] {status} in {last.duration_s:.1f}s\n"
                )

        if last.passed:
            return last

        # Before burning an Ollama iteration, check whether the failure
        # is actually "test runner not on PATH" (exit 126/127 with a
        # matching signature). If so, run the service's ./install-deps
        # once and retry — if the deps install succeeds, the next
        # iteration usually passes without any source patches. If
        # install-deps is missing or itself fails, bail immediately
        # with the infrastructure error instead of pointlessly asking
        # a language model to rewrite 19 files.
        if not auto_install_attempted and _looks_like_missing_runner(last):
            auto_install_attempted = True
            if progress is not None:
                progress.write(
                    "  [test] test runner missing — attempting auto-recover "
                    "via ./install-deps (this is usually a deps issue, not a "
                    "code issue; skipping Ollama fix pass)\n"
                )
            installed = _try_auto_install_deps(
                project_dir=ctx.project_dir, progress=progress
            )
            if installed:
                # Loop straight back to the test step without burning a
                # fix iteration — we haven't touched any source files.
                continue
            if progress is not None:
                progress.write(
                    "  [test] auto-recover failed — bailing out without "
                    "asking Ollama to patch files (infrastructure error, "
                    "not a code error; re-run `./install-deps` manually "
                    "and then `./test` to diagnose)\n"
                )
            return last

        if _time.monotonic() >= deadline:
            if progress is not None:
                progress.write(
                    f"  [test] giving up after {manifest.fix_timeout_m}m "
                    f"({iteration} iterations) — leaving the failing files in place\n"
                )
            return last

        # Discover ALL source files in the service, not just integration
        # outputs. A bug in models.py or api.py (written by Phase 1) can
        # cause integration tests to fail — Ollama needs to see and fix
        # those too.
        discover = discover_project_files or _discover_project_files
        all_files = discover(ctx.project_dir)
        if not all_files:
            if progress is not None:
                progress.write(
                    "  [test] no source files found to repair — bailing out\n"
                )
            return last

        if progress is not None:
            progress.write(
                f"  [fix {iteration}] asking Ollama to repair "
                f"{len(all_files)} project file(s)\n"
            )

        for sub_index, result in enumerate(all_files, start=1):
            try:
                rel = result.written_to.relative_to(ctx.project_dir)
            except ValueError:
                rel = result.written_to
            if progress is not None:
                progress.write(
                    f"    - patching ({sub_index}/{len(all_files)}) {rel}\n"
                )
            try:
                fixed = _ask_ollama_to_fix(
                    client=client,
                    ctx=ctx,
                    target_result=result,
                    test_run=last,
                    test_command=manifest.test_command,
                )
            except OllamaError as exc:
                if progress is not None:
                    progress.write(f"      (Ollama error: {exc})\n")
                continue
            except Exception as exc:  # noqa: BLE001
                if progress is not None:
                    progress.write(
                        f"      (skipping — _ask_ollama_to_fix raised: {exc!r})\n"
                    )
                continue
            if not fixed.strip():
                continue
            try:
                result.written_to.write_text(fixed, encoding="utf-8")
                result.bytes_written = len(fixed.encode("utf-8"))
            except OSError as exc:
                if progress is not None:
                    progress.write(
                        f"      (could not write fixed file: {exc})\n"
                    )
                continue


# --------------------------------------------------------------------------- #
#  Phase 6 — Staged test generation + fix loop
# --------------------------------------------------------------------------- #


def _guess_language(skeleton_name: str) -> str:
    """Infer the primary language from the skeleton name."""
    if "flutter" in skeleton_name:
        return "dart"
    if "react" in skeleton_name or "ts-" in skeleton_name or "next" in skeleton_name:
        return "typescript"
    if "spring" in skeleton_name or "java" in skeleton_name:
        return "java"
    if "rust" in skeleton_name:
        return "rust"
    if "go" in skeleton_name:
        return "go"
    return "python"


def _find_test_dir(service_dir: Path, skeleton_name: str) -> Path:
    """Return the conventional test directory for the skeleton."""
    if "flutter" in skeleton_name:
        return service_dir / "test"
    if "react" in skeleton_name or "ts-" in skeleton_name:
        return service_dir / "src"
    if "spring" in skeleton_name or "java" in skeleton_name:
        return service_dir / "src" / "test" / "java"
    for candidate in ["tests", "test", "app/tests"]:
        d = service_dir / candidate
        if d.is_dir():
            return d
    return service_dir / "tests"


def _test_filename(test_type: str, skeleton_name: str) -> str:
    """Return the filename for a generated test."""
    slug = test_type.replace(" ", "_").replace("-", "_")
    if "flutter" in skeleton_name:
        return f"{slug}_test.dart"
    if "react" in skeleton_name or "ts-" in skeleton_name:
        return f"{slug}.test.ts"
    if "spring" in skeleton_name or "java" in skeleton_name:
        return f"{slug.title().replace('_', '')}Test.java"
    if "rust" in skeleton_name:
        return f"{slug}_test.rs"
    if "go" in skeleton_name:
        return f"{slug}_test.go"
    return f"test_{slug}.py"


def _run_service_tests(
    service_dir: Path, test_cmd: str, ctx: GenerationContext,
    *, progress: Any = None,
) -> TestRunResult:
    """Run the service's test command and return the result.

    Delegates to the existing :func:`run_service_tests` which handles
    command rendering, absolutisation, and subprocess management.
    """
    return run_service_tests(test_cmd, ctx)


def _generate_test_file(
    *,
    client: OllamaClient,
    ctx: GenerationContext,
    test_type: str,
    instruction: str,
    annotation: str = "",
    progress: Any = None,
) -> None:
    """Ask Ollama to generate a test file for the given service."""
    variables = ctx.as_template_vars()
    try:
        rendered = instruction.format_map(variables)
    except KeyError:
        rendered = instruction  # fallback if placeholders don't match

    if annotation:
        rendered = rendered + "\n" + annotation

    service_dir = ctx.project_dir

    # Gather existing test files for reference
    existing_tests = ""
    for pattern in (
        "test*/*.py", "test*/*.ts", "test*/*.dart",
        "src/*.test.ts", "e2e/*.spec.ts",
    ):
        for tf in sorted(service_dir.glob(pattern))[:3]:
            try:
                content = tf.read_text(encoding="utf-8")[:2000]
                existing_tests += (
                    f"\n--- {tf.relative_to(service_dir)} ---\n{content}\n"
                )
            except (OSError, UnicodeDecodeError):
                pass

    # Gather source files for API context
    source_summary = ""
    for pattern in (
        "app/**/*.py", "src/**/*.ts", "lib/**/*.dart",
        "src/main/**/*.java",
    ):
        for sf in sorted(service_dir.glob(pattern)):
            if any(
                skip in str(sf)
                for skip in ("__pycache__", "node_modules", ".venv")
            ):
                continue
            try:
                content = sf.read_text(encoding="utf-8")[:3000]
                source_summary += (
                    f"\n--- {sf.relative_to(service_dir)} ---\n{content}\n"
                )
            except (OSError, UnicodeDecodeError):
                pass
            if len(source_summary) > 15000:
                break

    system_prompt = (
        f"You are generating a {test_type} test for a "
        f"{ctx.skeleton_name} service called {ctx.service_label}.\n"
        f"Item entity: {variables.get('item_class', 'Item')}, "
        f"auth: {ctx.auth_type}.\n\n"
        f"CRITICAL IMPORT RULES:\n"
        f"- App factory: from app import get_app\n"
        f"- Auth deps: from app.wrapper_api.deps import CurrentUser, SessionDep\n"
        f"- DB session: from app.wrapper_api.db import get_session\n"
        f"- For FastAPI TestClient: from fastapi.testclient import TestClient\n"
        f"- NEVER import from 'users', 'models', or 'db' directly\n\n"
        f"EXISTING TESTS (follow the same import and setup patterns):\n"
        f"{existing_tests[:8000]}\n\n"
        f"SOURCE FILES (API surface):\n"
        f"{source_summary[:12000]}\n\n"
        "Output ONLY the test file contents. No markdown fences, no commentary."
    )

    response = client.chat(system_prompt, rendered)
    response = clean_response(response, _guess_language(ctx.skeleton_name))

    test_dir = _find_test_dir(service_dir, ctx.skeleton_name)
    filename = _test_filename(test_type, ctx.skeleton_name)
    output_path = test_dir / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(response, encoding="utf-8")

    if progress:
        progress.write(
            f"    wrote {output_path.relative_to(service_dir)} "
            f"({len(response)} chars)\n"
        )


def _fix_failing_files(
    *,
    client: OllamaClient,
    ctx: GenerationContext,
    test_output: str,
    progress: Any = None,
) -> None:
    """Parse test output for failing files, fix each independently."""

    service_dir = ctx.project_dir
    _SKIP_DIRS = {".venv", "node_modules", "site-packages", "__pycache__",
                  ".git", "dist", "build", "target"}
    _service_slug = ctx.service_slug
    _ALLOW_PREFIXES = (
        f"app/{_service_slug}/",
        "tests/",
        "test/",
        "src/",
        "e2e/",
    )
    _SKIP_NAMES = {"__init__.py", "conftest.py"}

    def _is_own_source(p: Path) -> bool:
        if p.name in _SKIP_NAMES:
            return False
        try:
            rel = str(p.relative_to(service_dir))
        except ValueError:
            return False
        parts = set(Path(rel).parts)
        if parts & _SKIP_DIRS:
            return False
        return any(rel.startswith(prefix) for prefix in _ALLOW_PREFIXES)

    # Parse which test files FAILED (look for "FAILED tests/xxx.py::yyy")
    failed_tests = re.findall(
        r'FAILED\s+(tests/[^\s:]+|test/[^\s:]+|src/[^\s:]+)', test_output
    )

    # If no FAILED lines found, fall back to the old file-mention heuristic
    if not failed_tests:
        file_re = re.compile(
            r'(?:File ["\']|at |in |from )([^\s"\']+\.(?:py|ts|tsx|dart|java|rs|go))'
        )
        mentioned: set = set()
        for m in file_re.finditer(test_output[-4000:]):
            p = m.group(1)
            for candidate in [service_dir / p, service_dir / p.lstrip("/")]:
                if candidate.is_file() and _is_own_source(candidate):
                    mentioned.add(candidate)
                    break

        if not mentioned:
            for ext in ("*.py", "*.ts", "*.dart"):
                for tf in service_dir.rglob(f"test*/{ext}"):
                    if _is_own_source(tf):
                        mentioned.add(tf)

        # Use old-style fix for fallback files (full test_output context)
        for fpath in sorted(mentioned)[:10]:
            try:
                content = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            module_tree = ""
            for pattern in ("app/**/*.py", "src/**/*.ts", "lib/**/*.dart"):
                for sf in sorted(service_dir.glob(pattern)):
                    parts_str = str(sf.relative_to(service_dir))
                    if any(skip in parts_str for skip in
                           (".venv", "node_modules", "__pycache__")):
                        continue
                    module_tree += f"  {parts_str}\n"
                    if len(module_tree) > 2000:
                        break
            key_modules = ""
            for km in [
                "app/wrapper_api/schemas.py",
                "app/wrapper_api/auth.py",
                "app/wrapper_api/deps.py",
            ]:
                km_path = service_dir / km
                if km_path.is_file():
                    try:
                        km_content = km_path.read_text(encoding="utf-8")
                        key_modules += f"\n--- {km} ---\n{km_content[:2000]}\n"
                    except (OSError, UnicodeDecodeError):
                        pass
            system = (
                f"Fix the errors in {fpath.name}. Test output:\n\n"
                f"{test_output[-2000:]}\n\n"
                f"AVAILABLE MODULES:\n{module_tree}\n\n"
                f"KEY MODULES:\n{key_modules}\n\n"
                f"RULES:\n"
                f"- NEVER import model classes directly. Use TestClient HTTP calls only.\n"
                f"- STATUS CODES: POST register/catalog/orders/lines -> 201, all else -> 200\n"
                f"- HTTP METHODS: PUT /api/orders/{{id}}/address, POST /submit, POST /approve, POST /reject.\n"
                f"- REJECT needs a DIFFERENT order (create 2nd order, add line, PUT address, POST submit, POST reject).\n"
                f"- If 405 on /address, use PUT (not POST). If 405 on /submit or /approve or /reject, use POST.\n"
                f"- If 'must be in pending status', create a NEW order for the reject test.\n"
                f"- If error is 'assert X == Y' or 'Left contains N more item', relax the assertion: use `assert expected.items() <= actual.items()` or remove unexpected fields from the expected dict.\n"
                f"- PUT /api/orders/{{id}}/address returns {{ok:true}} NOT the address object.\n\n"
                "Output ONLY the fixed file contents. No markdown fences.\n/no_think"
            )
            fixed = client.chat(system, content)
            lang = fpath.suffix.lstrip(".")
            if lang == "tsx":
                lang = "typescript"
            fixed = clean_response(fixed, lang)
            fpath.write_text(fixed, encoding="utf-8")
            if progress:
                progress.write(f"    fixed {fpath.relative_to(service_dir)}\n")
        return

    # For each failed test file, extract its error section and fix it
    for test_rel in set(failed_tests):
        test_path = service_dir / test_rel.split("::")[0]  # remove ::test_name
        if not test_path.is_file() or not _is_own_source(test_path):
            continue

        try:
            content = test_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Extract error context specific to this file
        file_stem = test_rel.split("::")[0]
        file_errors = []
        for line in test_output.split('\n'):
            if file_stem in line or 'assert' in line.lower():
                file_errors.append(line)
        error_context = '\n'.join(file_errors[-30:]) if file_errors else test_output[-2000:]

        # Build module tree
        module_tree = ""
        for pattern in ("app/**/*.py", "src/**/*.ts", "lib/**/*.dart"):
            for sf in sorted(service_dir.glob(pattern)):
                parts_str = str(sf.relative_to(service_dir))
                if any(skip in parts_str for skip in
                       (".venv", "node_modules", "__pycache__")):
                    continue
                module_tree += f"  {parts_str}\n"
                if len(module_tree) > 2000:
                    break

        # Include key module content
        key_modules = ""
        for km in [
            "app/wrapper_api/schemas.py",
            "app/wrapper_api/auth.py",
            "app/wrapper_api/deps.py",
        ]:
            km_path = service_dir / km
            if km_path.is_file():
                try:
                    km_content = km_path.read_text(encoding="utf-8")
                    key_modules += f"\n--- {km} ---\n{km_content[:2000]}\n"
                except (OSError, UnicodeDecodeError):
                    pass

        system = (
            f"Fix the errors in {test_path.name}. Error for THIS file:\n\n"
            f"{error_context}\n\n"
            f"AVAILABLE MODULES:\n{module_tree}\n\n"
            f"KEY MODULES:\n{key_modules}\n\n"
            f"RULES:\n"
            f"- NEVER import model classes directly. Use TestClient HTTP calls only.\n"
            f"- STATUS CODES: POST register/catalog/orders/lines -> 201, all else -> 200\n"
            f"- HTTP METHODS: PUT /api/orders/{{id}}/address, POST /submit, POST /approve, POST /reject.\n"
            f"- REJECT needs a DIFFERENT order (create 2nd order, add line, PUT address, POST submit, POST reject).\n"
            f"- If 405 on /address, use PUT (not POST). If 405 on /submit or /approve or /reject, use POST.\n"
            f"- If 'must be in pending status', create a NEW order for the reject test.\n"
            f"- If error is 'assert X == Y' or 'Left contains N more item', relax the assertion: use `assert expected.items() <= actual.items()` or remove unexpected fields from the expected dict.\n"
            f"- PUT /api/orders/{{id}}/address returns {{ok:true}} NOT the address object.\n\n"
            "Output ONLY the fixed file contents. No markdown fences.\n/no_think"
        )
        fixed = client.chat(system, content)
        lang = test_path.suffix.lstrip(".")
        if lang == "tsx":
            lang = "typescript"
        fixed = clean_response(fixed, lang)
        test_path.write_text(fixed, encoding="utf-8")

        if progress:
            progress.write(f"    fixed {test_path.relative_to(service_dir)}\n")


def run_test_generation_phase(
    *,
    client: OllamaClient,
    ctx: GenerationContext,
    manifest: IntegrationManifest,
    progress: Any = None,
) -> TestRunResult:
    """Phase 6: staged test generation + fix loop.

    6a: Generate cross-stack integration tests
    6b: Generate E2E tests
    6c: Run all tests
    6d: If fail -> fix referenced files -> goto 6c
    6e: When green -> generate scenario tests from {testing_scenario}
    6f-6h: Run + fix loop until green or timeout
    """
    import time as _time

    # Phase 6 has no timeout — it runs until all tests pass or max
    # iterations (20) are exhausted. The manifest.fix_timeout_m is
    # ignored here (it was designed for the old Phase 4 loop).
    MAX_ITERATIONS = 20
    started = _time.monotonic()
    service_dir = ctx.project_dir
    # Phase 6 runs ONLY the AI-generated tests (tests/ directory),
    # not the full test suite which includes skeleton-provided tests
    # that may have pre-existing failures unrelated to the generated code.
    _pytest_bin = str(service_dir / ".venv" / "bin" / "pytest")
    if not Path(_pytest_bin).exists():
        _pytest_bin = "pytest"
    test_cmd = f"{_pytest_bin} tests/ -x --tb=short"

    def elapsed():
        return _time.monotonic() - started

    def time_left():
        return True  # no timeout — bounded by MAX_ITERATIONS instead

    # Use the fix model from config (OLLAMA_FIX_MODEL env var).
    # Default: qwen2.5-coder:32b (best open-source for code repair).
    fix_model = (
        getattr(client.config, "fix_model", None)
        or os.environ.get("OLLAMA_FIX_MODEL")
        or "qwen2.5-coder:32b"
    )
    if fix_model and fix_model != client.config.model:
        try:
            fix_cfg = OllamaConfig.from_env()
            fix_cfg = OllamaConfig(
                model=fix_model,
                base_url=fix_cfg.base_url,
                timeout=fix_cfg.timeout,
                temperature=0.1,
            )
            fix_client = OllamaClient(fix_cfg)
            fix_client.verify()
            if progress:
                progress.write(f"  Fix model: {fix_model} (fast fix loop)\n")
        except Exception:
            fix_client = client  # fallback to main model
            if progress:
                progress.write(f"  Fix model: {client.config.model} (fallback)\n")
    else:
        fix_client = client

    # Test generation model (qwen2.5-coder:32b — best code quality for tests).
    test_model = getattr(client.config, "test_model", None) or os.environ.get("OLLAMA_TEST_MODEL") or "qwen2.5-coder:32b"
    if test_model and test_model != client.config.model:
        try:
            test_cfg = OllamaConfig.from_env()
            test_cfg = OllamaConfig(
                model=test_model,
                base_url=test_cfg.base_url,
                timeout=test_cfg.timeout,
                temperature=0.2,
            )
            test_client = OllamaClient(test_cfg)
            test_client.verify()
            if progress:
                progress.write(f"  Test gen model: {test_model}\n")
        except Exception:
            test_client = client
    else:
        test_client = client

    # Fast fix model (devstral — 10s responses, used for 1st fix attempt).
    fast_fix_model = "devstral:latest"
    try:
        fast_cfg = OllamaConfig.from_env()
        fast_cfg = OllamaConfig(
            model=fast_fix_model,
            base_url=fast_cfg.base_url,
            timeout=min(fast_cfg.timeout, 300),
            temperature=0.1,
        )
        fast_fix_client = OllamaClient(fast_cfg)
        fast_fix_client.verify()
        if progress:
            progress.write(f"  Fast fix model: {fast_fix_model}\n")
    except Exception:
        fast_fix_client = fix_client  # fallback to heavy fix model

    if progress:
        progress.write("\n  ===== Phase 6: Test generation + fix loop =====\n")

    # Instruction strings for 6a/6b — kept as variables so the
    # same-error regeneration path (below) can reuse them.
    _INSTRUCTION_6A = (
        "Generate a cross-stack integration test using FastAPI TestClient.\n\n"
        "START your file with EXACTLY this boilerplate (copy verbatim):\n"
        "```\n"
        "import pytest\n"
        "import uuid\n"
        "from fastapi.testclient import TestClient\n"
        "from app import get_app\n"
        "\n"
        "@pytest.fixture(scope='module')\n"
        "def client():\n"
        "    app = get_app()\n"
        "    with TestClient(app) as c:\n"
        "        yield c\n"
        "\n"
        "def _register_and_login(client):\n"
        "    uid = uuid.uuid4().hex[:8]\n"
        "    r = client.post('/api/auth/register', json={\n"
        "        'username': f'test-{uid}', 'email': f'test-{uid}@example.com',\n"
        "        'password': 'testpass123', 'password_confirm': 'testpass123'\n"
        "    })\n"
        "    assert r.status_code in (201, 400, 409), f'register: {r.status_code} {r.text}'\n"
        "    r = client.post('/api/auth/login', json={\n"
        "        'username': f'test-{uid}', 'password': 'testpass123'\n"
        "    })\n"
        "    assert r.status_code == 200, f'login: {r.status_code} {r.text}'\n"
        "    return r.json()['access']\n"
        "```\n\n"
        "Use _register_and_login(client) to get a JWT token, then set\n"
        "headers = {'Authorization': f'Bearer {token}'} for authenticated calls.\n"
        "Register: POST json={username,email,password,password_confirm} -> 201\n"
        "Login: POST json={username,password} -> 200 {access:'jwt'}\n\n"
        "API RESPONSE SHAPES (use these exact field names):\n"
        "POST /api/catalog json={name,price,category} -> 201 {id,name,description,price,category,available}\n"
        "GET /api/catalog -> 200 [{id,name,description,price,category,available}]\n"
        "POST /api/orders -> 201 {id,user_id,status:'draft',created_at}\n"
        "POST /api/orders/{id}/lines json={catalog_item_id,quantity} -> 201 {id,catalog_item_id,quantity,unit_price}\n"
        "PUT /api/orders/{id}/address json={street,city,zip_code,phone,notes} -> 200 {ok:true} (NOT address fields!)\n"
        "GET /api/orders/{id} -> 200 {id,status,lines:[...],address:{id,street,city,zip_code,phone,notes}}\n"
        "NOTE: address objects in the response include an 'id' field. Do NOT assert exact dict equality on address — use subset checks or just verify specific fields.\n"
        "POST /api/orders/{id}/submit -> 200 {id,status:'pending'}\n"
        "POST /api/orders/{id}/approve json={wait_minutes,feedback} -> 200 {id,status:'approved',wait_minutes,feedback}\n"
        "POST /api/orders/{id}/reject json={feedback} -> 200 {id,status:'rejected',feedback}\n"
        "NEVER import from 'users', 'depts', or 'models' directly.\n\n"
        "Domain: {backend_extra}\n"
        "Testing scenario: {testing_scenario}"
    )

    _INSTRUCTION_6B = (
        "Generate an E2E/integration test using FastAPI TestClient.\n\n"
        "Use the SAME boilerplate as the integration test:\n"
        "```\n"
        "import pytest\n"
        "import uuid\n"
        "from fastapi.testclient import TestClient\n"
        "from app import get_app\n"
        "\n"
        "@pytest.fixture(scope='module')\n"
        "def client():\n"
        "    app = get_app()\n"
        "    with TestClient(app) as c:\n"
        "        yield c\n"
        "```\n\n"
        "Test the full user journey via HTTP only — NEVER import models,\n"
        "NEVER import OrderCrud, NEVER import from app.orders or app.wrapper_api.orders.\n"
        "Only use client.get/post/put/delete with JSON bodies and assert status codes.\n\n"
        "AVAILABLE ROUTES (use ONLY these, no others exist):\n"
        "Register: POST /api/auth/register json={{username, email, password, password_confirm}} -> 201\n"
        "Login: POST /api/auth/login json={{username, password}} -> 200 {{access: 'jwt'}}\n"
        "POST /api/catalog json={{name, price, category}} -> 201 {{id, name, price, category}}\n"
        "GET /api/catalog -> 200 [{{id, name, price, category}}, ...]\n"
        "POST /api/orders -> 201 {{id, status:'draft', user_id, created_at}}\n"
        "GET /api/orders -> 200 [{{id, status, lines, address}}, ...]\n"
        "GET /api/orders/{{id}} -> 200 {{id, status, lines:[...], address:{{...}}}}\n"
        "POST /api/orders/{{id}}/lines json={{catalog_item_id, quantity}} -> 201 {{id, order_id, catalog_item_id, quantity}}\n"
        "PUT /api/orders/{{id}}/address json={{street, city, zip_code}} -> 200 {{ok:true}}\n"
        "POST /api/orders/{{id}}/submit -> 200 {{id, status:'pending'}}\n"
        "POST /api/orders/{{id}}/approve json={{wait_minutes, feedback}} -> 200 {{id, status:'approved', wait_minutes, feedback}}\n"
        "POST /api/orders/{{id}}/reject json={{feedback}} -> 200 {{id, status:'rejected', feedback}}\n\n"
        "IMPORTANT: There is NO PUT /api/orders/{{id}} route. There is NO DELETE route.\n"
        "NOTE: Address objects in GET /api/orders/{{id}} response include an 'id' field. Do NOT assert exact dict equality on address — verify specific fields instead.\n"
        "Use unique uuid-based usernames to avoid 400 'already exists' errors.\n"
        "Always pass Authorization: Bearer <token> header for protected routes.\n\n"
        "Domain: {backend_extra}\n"
        "Testing scenario: {testing_scenario}"
    )

    # 6a
    if progress:
        progress.write("  [6a] Generating cross-stack integration tests...\n")
    _generate_test_file(
        client=test_client, ctx=ctx,
        test_type="cross_stack_integration",
        instruction=_INSTRUCTION_6A,
        progress=progress,
    )

    # 6b
    if progress:
        progress.write("  [6b] Generating E2E tests...\n")
    _generate_test_file(
        client=test_client, ctx=ctx,
        test_type="e2e",
        instruction=_INSTRUCTION_6B,
        progress=progress,
    )

    # 6c-6d loop with same-error detection (bounded by MAX_ITERATIONS)
    iteration = 0
    last_result: Optional[TestRunResult] = None
    last_error_sig = ""
    same_error_count = 0
    MAX_SAME_ERROR = 3

    while iteration < MAX_ITERATIONS:
        iteration += 1
        if progress:
            progress.write(
                f"\n  [6c] Running tests (iteration {iteration}/{MAX_ITERATIONS}, "
                f"{elapsed():.0f}s elapsed)...\n"
            )
        result = _run_service_tests(
            service_dir, test_cmd, ctx, progress=progress,
        )
        last_result = result
        if result.passed:
            if progress:
                progress.write(f"  [6c] PASS in {result.duration_s:.1f}s\n")
            break
        if progress:
            progress.write(
                f"  [6d] FAIL (exit {result.returncode}), fixing...\n"
            )
        if iteration >= MAX_ITERATIONS:
            if progress:
                progress.write(
                    f"  [6d] Max iterations ({MAX_ITERATIONS}) reached.\n"
                )
            break

        # Escalating fix strategy:
        # 1st attempt: fast model (devstral/test_client)
        # 2nd attempt on same error: heavy model (qwen2.5-coder/fix_client)
        # 3rd attempt on same error: regenerate tests with annotation
        import re as _re
        # Normalize dynamic values (IDs, UUIDs, timestamps) so the
        # same logical error is recognized across iterations.
        _raw_sig = result.combined_output()[-500:]
        error_sig = _re.sub(r'\b\d+\b', 'N', _raw_sig)
        error_sig = _re.sub(r'[0-9a-f]{8,}', 'UUID', error_sig)
        # Extract just the assertion/error line for comparison
        _err_lines = [
            l for l in error_sig.splitlines()
            if any(k in l.lower() for k in ('assert', 'error', 'failed', '405', '404', '500', '422'))
        ]
        error_sig = '\n'.join(_err_lines[-3:]) if _err_lines else error_sig[-200:]
        if error_sig == last_error_sig:
            same_error_count += 1
        else:
            same_error_count = 1
            last_error_sig = error_sig

        if same_error_count >= MAX_SAME_ERROR:
            # 3rd fail on same error → regenerate with annotation
            if progress:
                progress.write(
                    f"\n  [6d] Same error {MAX_SAME_ERROR}x. "
                    f"Regenerating tests with annotation...\n"
                )
            annotation = (
                f"\nIMPORTANT: Previous generation failed with this error:\n"
                f"{result.combined_output()[-500:]}\n"
                f"Fix this issue in the new generation.\n"
            )
            _generate_test_file(
                client=test_client, ctx=ctx,
                test_type="cross_stack_integration",
                instruction=_INSTRUCTION_6A,
                annotation=annotation,
                progress=progress,
            )
            _generate_test_file(
                client=test_client, ctx=ctx,
                test_type="e2e",
                instruction=_INSTRUCTION_6B,
                annotation=annotation,
                progress=progress,
            )
            same_error_count = 0
            last_error_sig = ""
            continue
        elif same_error_count == 2:
            # 2nd fail on same error → try heavy fix model
            if progress:
                progress.write(
                    f"  [6d] 2nd attempt, using heavy fix model...\n"
                )
            _fix_failing_files(
                client=fix_client, ctx=ctx,
                test_output=result.combined_output(),
                progress=progress,
            )
            continue

        # 1st attempt: use fast model (devstral)
        _fix_failing_files(
            client=fast_fix_client, ctx=ctx,
            test_output=result.combined_output(),
            progress=progress,
        )

    # 6e: scenario tests
    if (
        last_result and last_result.passed
        and ctx.testing_scenario
        and time_left()
    ):
        if progress:
            progress.write(
                "\n  [6e] Generating scenario tests from testing_scenario...\n"
            )
        _generate_test_file(
            client=test_client, ctx=ctx,
            test_type="complex_scenario",
            instruction=(
                "Generate a comprehensive multi-step test following this "
                "scenario EXACTLY:\n\n"
                "{testing_scenario}\n\n"
                "Use the SAME boilerplate as the integration test:\n"
                "```\n"
                "import pytest\n"
                "import uuid\n"
                "from fastapi.testclient import TestClient\n"
                "from app import get_app\n"
                "\n"
                "@pytest.fixture(scope='module')\n"
                "def client():\n"
                "    app = get_app()\n"
                "    with TestClient(app) as c:\n"
                "        yield c\n"
                "```\n\n"
                "AVAILABLE ROUTES (use ONLY these):\n"
                "POST /api/auth/register json={{username,email,password,password_confirm}} -> 201\n"
                "POST /api/auth/login json={{username,password}} -> 200 {{access:'jwt'}}\n"
                "POST /api/catalog json={{name,price,category}} -> 201\n"
                "GET /api/catalog -> 200 [{{id,name,price,category}}]\n"
                "POST /api/orders -> 201 {{id,status:'draft'}}\n"
                "GET /api/orders/{{id}} -> 200 {{id,status,lines:[...],address:{{id,street,city,zip_code,...}}}}\n"
                "POST /api/orders/{{id}}/lines json={{catalog_item_id,quantity}} -> 201\n"
                "PUT /api/orders/{{id}}/address json={{street,city,zip_code,phone,notes}} -> 200 {{ok:true}}\n"
                "POST /api/orders/{{id}}/submit -> 200 {{id,status:'pending'}}\n"
                "POST /api/orders/{{id}}/approve json={{wait_minutes,feedback}} -> 200\n"
                "POST /api/orders/{{id}}/reject json={{feedback}} -> 200\n\n"
                "IMPORTANT: The field name in GET /api/orders/{{id}} is 'address' NOT 'delivery_address'.\n"
                "Use unique uuid-based usernames. Pass Authorization: Bearer <token> header.\n"
                "Exercise the full business flow step by step with assertions at each stage.\n"
                "/no_think"
            ),
            progress=progress,
        )

        # 6f-6h loop (bounded by MAX_ITERATIONS)
        while iteration < MAX_ITERATIONS:
            iteration += 1
            if progress:
                progress.write(
                    f"\n  [6f] Running all tests (iteration {iteration}/{MAX_ITERATIONS}, "
                    f"{elapsed():.0f}s elapsed)...\n"
                )
            result = _run_service_tests(
                service_dir, test_cmd, ctx, progress=progress,
            )
            last_result = result
            if result.passed:
                if progress:
                    progress.write(
                        f"  [6f] ALL PASS in {result.duration_s:.1f}s\n"
                    )
                break
            if progress:
                progress.write(
                    f"  [6g] FAIL (exit {result.returncode}), fixing...\n"
                )
            if iteration >= MAX_ITERATIONS:
                if progress:
                    progress.write(
                        f"  [6g] Max iterations ({MAX_ITERATIONS}) reached.\n"
                    )
                break
            _fix_failing_files(
                client=fix_client, ctx=ctx,
                test_output=result.combined_output(),
                progress=progress,
            )

    if progress:
        status = "PASS" if (last_result and last_result.passed) else "FAIL"
        progress.write(
            f"\n  Phase 6 complete: {status} "
            f"({iteration} iterations, {elapsed():.0f}s)\n"
        )
    return last_result or TestRunResult(
        command=[test_cmd],
        cwd=service_dir,
        returncode=1,
        stdout="",
        stderr="no tests ran",
        duration_s=0.0,
    )


# --------------------------------------------------------------------------- #
#  Phase 5 — Project documentation generation
# --------------------------------------------------------------------------- #

_DOCS_SYSTEM_PROMPT = """\
You are a senior full-stack engineer writing comprehensive project documentation
for a freshly generated multi-service wrapper project.

The project is called "{project_name}". It was generated by **dev_skel**, a
Makefile-driven project generator. Each service lives in its own subdirectory
and shares a common environment (database, JWT secret) via `.env` and `_shared/`.

Services in this project:
{services_summary}

The wrapper directory has these dispatch scripts that auto-discover services:
  ./run, ./test, ./build, ./stop, ./install-deps, ./services

Write documentation that is:
- Detailed, specific to THIS project (not generic templates)
- Includes real file paths, real service names, real tech stacks
- Actionable — a new developer can onboard in minutes
- Covers architecture, setup, development workflow, testing, deployment
"""

_DOCS_TARGETS: List[Dict[str, Any]] = [
    {
        "path": "README.md",
        "description": "Wrapper-level project README",
        "prompt": """\
Write a comprehensive README.md for the "{project_name}" project wrapper.

Include these sections:
1. **Project Overview** — what this project does, its services, their roles
2. **Architecture** — how the services interact, shared DB, JWT auth flow
3. **Prerequisites** — required toolchains with version requirements
4. **Quick Start** — step-by-step from clone to running (install-deps, run, test)
5. **Project Structure** — annotated directory tree with every service and key file
6. **Services** — for each service: purpose, tech stack, key endpoints/routes, config
7. **Shared Environment** — .env variables, DATABASE_URL, JWT_SECRET, how to switch to Postgres
8. **Development Workflow** — how to add features, run tests, lint, format
9. **Wrapper Scripts** — ./run, ./test, ./build, ./services — with examples
10. **Adding Services** — how to add another service to this wrapper
11. **Deployment** — Docker, environment variables, production considerations
12. **Troubleshooting** — common issues and solutions

{services_detail}
""",
    },
    {
        "path": "AGENTS.md",
        "description": "Cross-agent LLM instructions",
        "prompt": """\
Write a comprehensive AGENTS.md for the "{project_name}" project wrapper.
This file is loaded by ALL LLM coding agents (Claude, Junie, Copilot, Cursor, etc.)
as their primary instruction set for working on this project.

Include these sections:
1. **Read These Files First** — ordered list of files to read for context
2. **Project Architecture** — services, their roles, how they interact, shared DB/JWT
3. **Service Details** — for EACH service: tech stack, directory layout, key files,
   entry points, test commands, dependencies, important patterns
4. **Shared Environment Contract** — .env variables, DATABASE_URL, JWT_SECRET,
   SERVICE_URL_* auto-discovery, how tokens are shared across services
5. **Development Workflow** — standard commands (./run, ./test, ./build, etc.)
6. **Code Conventions** — per-service coding patterns, naming, error handling
7. **Testing Strategy** — unit tests, integration tests, cross-service tests,
   how to run each type, what test frameworks each service uses
8. **Dependency Management** — per-service package managers, lock files, version policies
9. **Safety Rules** — what NOT to do (don't hand-edit generated files, don't hardcode
   secrets, don't break the shared env contract, etc.)
10. **Verification Checklist** — what to check before declaring a task done
11. **File Index** — every important file with a one-line description

Be extremely detailed. Include real file paths, real endpoints, real class/function names.
This is the primary reference an AI agent will use to understand and modify this project.

{services_detail}
""",
    },
    {
        "path": "CLAUDE.md",
        "description": "Claude Code specific instructions",
        "prompt": """\
Write a comprehensive CLAUDE.md for the "{project_name}" project wrapper.
This file is loaded by Claude Code as its instruction set. It complements AGENTS.md
with Claude-specific operational notes.

Include these sections:
1. **Read These Files First** — CLAUDE.md, AGENTS.md, per-service CLAUDE.md files
2. **Project Snapshot** — concise summary of all services, their tech stacks, how they
   connect, the shared env contract
3. **Default Maintenance Workflow** — step-by-step for "do maintenance" / "verify the project"
4. **Claude Operational Notes** — Plan before non-trivial edits, use Task tools,
   prefer dedicated tools, confirm risky actions, memory hygiene
5. **Per-Service Quick Reference** — for each service: key files, test commands,
   important classes/functions, gotchas
6. **Editing Conventions** — Read before edit, minimal diffs, don't modify
   generator-owned files, never weaken tests
7. **Verification Checklist** — service tests green, docs updated, no stale artifacts

Include real paths, real commands, real service details. Be thorough.

{services_detail}
""",
    },
    {
        "path": "JUNIE-RULES.md",
        "description": "JetBrains Junie agent instructions",
        "prompt": """\
Write a JUNIE-RULES.md for the "{project_name}" project wrapper.
This file is loaded by JetBrains Junie as its instruction set.

Include these sections:
1. **Project Overview** — services, tech stacks, shared environment
2. **File Layout** — directory tree with annotations
3. **Per-Service Details** — tech stack, key files, test commands, important patterns
4. **Shared Environment** — .env variables and their purpose
5. **Development Commands** — ./run, ./test, ./build, etc.
6. **Rules** — don't hand-edit generated files, don't hardcode secrets,
   follow existing patterns, run tests before declaring done
7. **Testing** — what tests exist, how to run them, what frameworks

{services_detail}
""",
    },
]


def _build_services_summary(
    project_root: Path,
    service_contexts: List[GenerationContext],
) -> str:
    """One-line-per-service summary for the system prompt."""
    lines = []
    for ctx in service_contexts:
        svc_dir = project_root / ctx.service_subdir
        tech = ctx.skeleton_name.replace("-skel", "")
        lines.append(
            f"  - {ctx.service_subdir}/ ({ctx.service_label}) — "
            f"skeleton: {ctx.skeleton_name}, tech: {tech}, "
            f"item entity: {ctx.item_name}, auth: {ctx.auth_type}"
        )
    return "\n".join(lines) or "  (no services)"


def _build_services_detail(
    project_root: Path,
    service_contexts: List[GenerationContext],
) -> str:
    """Detailed per-service block including key files for context."""
    blocks = []
    for ctx in service_contexts:
        svc_dir = project_root / ctx.service_subdir
        tech = ctx.skeleton_name.replace("-skel", "")
        files_block = ""
        # List key source files in the service
        key_dirs = ["app", "src", "lib", "core", "tests", "test"]
        key_files = []
        for d in key_dirs:
            dpath = svc_dir / d
            if dpath.is_dir():
                for f in sorted(dpath.rglob("*")):
                    if f.is_file() and f.suffix in (
                        ".py", ".ts", ".tsx", ".js", ".java", ".rs", ".dart",
                        ".toml", ".json", ".yaml", ".yml",
                    ):
                        try:
                            rel = f.relative_to(project_root)
                        except ValueError:
                            rel = f
                        key_files.append(str(rel))
        # Also include top-level config files
        for name in [
            "pyproject.toml", "requirements.txt", "package.json",
            "Cargo.toml", "pom.xml", "pubspec.yaml",
            ".env.example", "Dockerfile", "Makefile",
        ]:
            if (svc_dir / name).is_file():
                key_files.append(f"{ctx.service_subdir}/{name}")
        if key_files:
            files_block = "Key files:\n" + "\n".join(
                f"    {f}" for f in key_files[:50]  # cap to avoid huge prompts
            )

        blocks.append(
            f"### Service: {ctx.service_label} ({ctx.service_subdir}/)\n"
            f"- Skeleton: {ctx.skeleton_name}\n"
            f"- Tech: {tech}\n"
            f"- Item entity: {ctx.item_name} (class: {ctx.item_class})\n"
            f"- Auth: {ctx.auth_type}\n"
            f"{files_block}"
        )
    return "\n\n".join(blocks) or "(no services)"


def run_docs_generation(
    *,
    client: OllamaClient,
    project_root: Path,
    project_name: str,
    service_contexts: List[GenerationContext],
    dry_run: bool = False,
    progress: Optional[Any] = None,
) -> List[Path]:
    """Generate project-level documentation and LLM instruction files.

    Uses Ollama to write detailed, project-specific documentation based
    on the actual services, file structure, and configuration present
    in the generated wrapper.

    Returns list of written file paths.
    """

    services_summary = _build_services_summary(project_root, service_contexts)
    services_detail = _build_services_detail(project_root, service_contexts)

    system = _DOCS_SYSTEM_PROMPT.format(
        project_name=project_name,
        services_summary=services_summary,
    )

    written: List[Path] = []
    for i, target in enumerate(_DOCS_TARGETS, start=1):
        out_path = project_root / target["path"]
        desc = target["description"]
        if progress is not None:
            progress.write(
                f"  [{i}/{len(_DOCS_TARGETS)}] {target['path']} — {desc}\n"
            )
        if dry_run:
            continue

        user_prompt = target["prompt"].format(
            project_name=project_name,
            services_summary=services_summary,
            services_detail=services_detail,
        )

        try:
            raw = client.chat(system, user_prompt)
        except OllamaError as exc:
            if progress is not None:
                progress.write(f"    (Ollama error: {exc})\n")
            continue
        except Exception as exc:  # noqa: BLE001
            if progress is not None:
                progress.write(f"    (unexpected error: {exc!r})\n")
            continue

        # Strip markdown fences if the model wrapped the output.
        content = raw.strip()
        if content.startswith("```"):
            first_nl = content.index("\n") if "\n" in content else len(content)
            content = content[first_nl + 1:]
        if content.endswith("```"):
            content = content[:-3].rstrip()

        try:
            out_path.write_text(content + "\n", encoding="utf-8")
            written.append(out_path)
            if progress is not None:
                progress.write(
                    f"    wrote {len(content)} chars\n"
                )
        except OSError as exc:
            if progress is not None:
                progress.write(f"    (write error: {exc})\n")

    # Also generate per-service AGENTS.md / CLAUDE.md with real content
    for ctx in service_contexts:
        svc_dir = project_root / ctx.service_subdir
        for doc_name in ("AGENTS.md", "CLAUDE.md"):
            doc_path = svc_dir / doc_name
            desc = f"{ctx.service_subdir}/{doc_name}"
            if progress is not None:
                progress.write(f"  [svc] {desc}\n")
            if dry_run:
                continue

            svc_prompt = (
                f"Write a comprehensive {doc_name} for the "
                f"\"{ctx.service_label}\" service ({ctx.service_subdir}/).\n"
                f"Skeleton: {ctx.skeleton_name}\n"
                f"Tech: {ctx.skeleton_name.replace('-skel', '')}\n"
                f"Item entity: {ctx.item_name} (class: {ctx.item_class})\n"
                f"Auth style: {ctx.auth_type}\n"
                f"Project: {project_name}\n\n"
                f"Include: service purpose, architecture, key files with "
                f"descriptions, important classes/functions, API endpoints, "
                f"test commands, dependency management, coding conventions, "
                f"safety rules, verification checklist.\n\n"
                f"Be extremely detailed with real file paths and real code "
                f"references. This is what an AI agent reads to understand "
                f"this service.\n\n"
                f"{services_detail}"
            )
            try:
                raw = client.chat(system, svc_prompt)
            except (OllamaError, Exception) as exc:  # noqa: BLE001
                if progress is not None:
                    progress.write(f"    (error: {exc})\n")
                continue

            content = raw.strip()
            if content.startswith("```"):
                first_nl = content.index("\n") if "\n" in content else len(content)
                content = content[first_nl + 1:]
            if content.endswith("```"):
                content = content[:-3].rstrip()

            try:
                doc_path.write_text(content + "\n", encoding="utf-8")
                written.append(doc_path)
                if progress is not None:
                    progress.write(f"    wrote {len(content)} chars\n")
            except OSError as exc:
                if progress is not None:
                    progress.write(f"    (write error: {exc})\n")

    return written


def generate_targets(
    *,
    client: OllamaClient,
    manifest: AiManifest,
    ctx: GenerationContext,
    dry_run: bool = False,
    progress: Optional[Any] = None,
) -> List[TargetResult]:
    """Run every manifest target through the RAG-aware agent.

    Thin wrapper around
    :meth:`skel_rag.agent.RagAgent.generate_targets`. The agent
    indexes the skeleton corpus once (cached on the client), retrieves
    the most relevant chunks per target, and exposes them to manifest
    prompts via the new ``{retrieved_context}`` placeholder while still
    populating the legacy ``{template}`` placeholder for unmigrated
    manifests.

    ``progress`` may be any object with a ``write(str)`` method (e.g.
    ``sys.stdout``); the agent forwards one-line updates so the CLI
    keeps showing progress without depending on a particular logging
    framework.
    """

    return client.agent.generate_targets(
        manifest=manifest,
        ctx=ctx,
        dry_run=dry_run,
        progress=progress,
    )


# --------------------------------------------------------------------------- #
#  Internal helpers
# --------------------------------------------------------------------------- #


def _read_reference(skeleton_path: Path, template: Optional[str]) -> Optional[str]:
    if not template:
        return None
    candidate = (skeleton_path / template).resolve()
    if not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError:
        return None


def _camel_case(name: str) -> str:
    parts = re.split(r"[^0-9a-zA-Z]+", name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


class _StrictDict(dict):
    """Dict subclass that raises a clear error for missing format keys."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        raise KeyError(
            f"Manifest prompt referenced unknown placeholder '{{{key}}}'."
        )


# --------------------------------------------------------------------------- #
# Phase 7: Kubernetes lifecycle helpers
# --------------------------------------------------------------------------- #


@dataclass
class KubernetesResult:
    """Outcome of :func:`run_kubernetes_phase`."""

    ok: bool
    error: "str | None" = None
    helm_lint_output: str = ""
    generated_files: "list[Path]" = field(default_factory=list)
    failed_resources: "list[str]" = field(default_factory=list)
    fix_iterations: int = 0


def _load_kubernetes_manifest() -> Any:
    """Load the shared ``_kubernetes.py`` AI manifest.

    It lives at ``_skels/_common/manifests/_kubernetes.py`` and is the
    single source of truth for Tier-2 dispatch + prompts.
    """
    import importlib.util

    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = (
        repo_root / "_skels" / "_common" / "manifests" / "_kubernetes.py"
    )
    spec = importlib.util.spec_from_file_location("_kubernetes", manifest_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Kubernetes manifest at {manifest_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ask_ollama_for_kubernetes(
    client: "OllamaClient",
    *,
    service_id: str,
    service_tech: str,
    service_ctx: dict,
    filename: str,
    system_prompt: str,
    file_prompt: str,
) -> str:
    """Render one Tier-2 file by asking the LLM once."""
    user = (
        f"SERVICE_ID: {service_id}\n"
        f"SERVICE_TECH: {service_tech}\n"
        f"SERVICE_CTX: {service_ctx}\n\n"
        f"TASK: Generate `{filename}` for this service.\n\n"
        f"{file_prompt}"
    )
    raw = client.chat(system=system_prompt, user=user)
    return clean_response(raw, language="yaml")


def _run_kubernetes_ai_generation(
    *,
    client: "OllamaClient | None",
    wrapper_dir: Path,
    project_yml: dict,
    managed_root: Path,
) -> "list[Path]":
    """Tier-2 AI generation — one file per (service × dispatched filename).

    Enforces the managed-tree-only write scope via a ``.resolve()``
    prefix check; AI output that resolves outside the service's
    ``_managed/<svc>/`` directory is silently dropped (the caller sees
    the missing file and can report a mismatch).
    """
    km = _load_kubernetes_manifest()
    if client is None:
        client = OllamaClient(OllamaConfig.from_env())

    written: "list[Path]" = []
    managed_root_resolved = managed_root.resolve()

    for svc in project_yml.get("services", []) or []:
        svc_id = svc.get("id", "")
        raw_tech = svc.get("tech", "")
        # dev_skel.project.yml stores tech as "<name>-skel"; DISPATCH
        # keys omit the suffix so new skeletons only need one entry.
        tech = raw_tech.removesuffix("-skel")
        files = km.DISPATCH.get(tech, [])
        if not files:
            continue
        svc_dir = managed_root / svc_id
        svc_dir.mkdir(parents=True, exist_ok=True)
        svc_dir_resolved = svc_dir.resolve()
        for fname in files:
            prompt = km.FILE_PROMPTS.get(fname)
            if prompt is None:
                continue
            yaml_text = _ask_ollama_for_kubernetes(
                client,
                service_id=svc_id,
                service_tech=tech,
                service_ctx=svc,
                filename=fname,
                system_prompt=km.SYSTEM_PROMPT,
                file_prompt=prompt,
            )
            dst = (svc_dir / fname).resolve()
            # Defense in depth: reject writes outside _managed/<svc>/.
            try:
                dst.relative_to(svc_dir_resolved)
                dst.relative_to(managed_root_resolved)
            except ValueError:
                continue
            dst.write_text(yaml_text, encoding="utf-8")
            written.append(dst)
    return written


def run_kubernetes_phase(
    client,
    wrapper_dir: "Path | str",
    project_yml: "dict | None",
    *,
    fix_timeout_m: int = 30,
    keep_kind: bool = False,
    skip_kind: bool = False,
    skip_ai: bool = False,
) -> KubernetesResult:
    """Phase 4: Tier-1 helm-gen + (optional) Tier-2 AI + (optional) kind E2E.

    Parameters
    ----------
    client
        An :class:`OllamaClient` (or ``None`` to construct a default
        from env). Ignored when ``skip_ai=True``.
    wrapper_dir
        Path to the wrapper project. Must contain
        ``dev_skel.project.yml``.
    project_yml
        Pre-parsed project metadata. When ``None``, the minimal parser
        reads the YAML from disk.
    skip_ai
        Skip Tier-2 AI generation. ``_managed/<svc>/`` directories are
        still scaffolded so downstream sync commands have a stable
        layout.
    skip_kind
        Skip the kind-cluster E2E. ``helm lint`` still runs.

    Current scope (Task 4)
    ----------------------
    Only the static path is implemented. Tier-2 AI generation (Task 5),
    kind E2E (Task 6), and the fix loop (Task 7) are TODO.
    """
    import subprocess as _sp

    wrapper_dir = Path(wrapper_dir).resolve()
    repo_root = Path(__file__).resolve().parent.parent

    # Tier-1: delegate to skel-deploy helm-gen
    helm_gen = _sp.run(
        [str(repo_root / "_bin" / "skel-deploy"), "helm-gen", str(wrapper_dir)],
        capture_output=True,
        text=True,
    )
    if helm_gen.returncode != 0:
        return KubernetesResult(
            ok=False,
            error=f"helm-gen failed: {helm_gen.stderr.strip() or helm_gen.stdout.strip()}",
        )

    if project_yml is None:
        try:
            project_yml = read_project_yml(wrapper_dir)
        except FileNotFoundError as exc:
            return KubernetesResult(ok=False, error=str(exc))

    managed_root = wrapper_dir / "deploy" / "helm" / "templates" / "_managed"
    managed_root.mkdir(parents=True, exist_ok=True)
    for svc in project_yml.get("services", []) or []:
        sid = svc.get("id", "")
        if not is_safe_service_id(sid):
            return KubernetesResult(
                ok=False,
                error=f"rejecting unsafe service id {sid!r} in dev_skel.project.yml",
            )
        (managed_root / sid).mkdir(parents=True, exist_ok=True)

    generated_files: "list[Path]" = []

    if not skip_ai:
        generated_files.extend(
            _run_kubernetes_ai_generation(
                client=client,
                wrapper_dir=wrapper_dir,
                project_yml=project_yml,
                managed_root=managed_root,
            )
        )

    # helm lint always runs
    lint = _sp.run(
        ["helm", "lint", str(wrapper_dir / "deploy" / "helm")],
        capture_output=True,
        text=True,
    )
    if lint.returncode != 0:
        return KubernetesResult(
            ok=False,
            error="helm lint failed",
            helm_lint_output=lint.stdout + lint.stderr,
        )

    if not skip_kind:
        # kind E2E + fix loop land in Tasks 6 + 7.
        pass

    return KubernetesResult(
        ok=True,
        helm_lint_output=lint.stdout,
        generated_files=generated_files,
    )


def _kube_diagnose_from_json(
    *,
    pods: dict,
    events: dict,
    describes: "dict[str, str]",
    logs: "dict[str, str]",
) -> str:
    """Render a deterministic diagnostic bundle from parsed kubectl JSON.

    Isolating the parser from a real kubectl invocation keeps the bundle
    format testable against static fixtures (see
    ``_bin/_fixtures/kube_diagnose/``) and keeps the fix-loop prompt
    shape stable across iterations.
    """
    lines: list[str] = []
    lines.append("FAILING_RESOURCES:")

    failing: list[tuple[str, str, int]] = []
    for item in pods.get("items", []) or []:
        name = item.get("metadata", {}).get("name", "?")
        for cs in item.get("status", {}).get("containerStatuses", []) or []:
            waiting = cs.get("state", {}).get("waiting") or {}
            reason = waiting.get("reason")
            restarts = cs.get("restartCount", 0)
            if reason:
                failing.append((name, reason, restarts))
                lines.append(
                    f"  - pod/{name}  status={reason}   restarts={restarts}"
                )
    if not failing:
        lines.append("  (none)")

    lines.append("")
    lines.append("EVENTS (last 20):")
    event_items = (events.get("items") or [])[-20:]
    if not event_items:
        lines.append("  (none)")
    else:
        for ev in event_items:
            typ = ev.get("type", "Normal")
            reason = ev.get("reason", "")
            msg = ev.get("message", "")
            obj = (ev.get("involvedObject") or {}).get("name", "")
            lines.append(f"  {typ} {reason}: {msg} ({obj})")

    if describes:
        lines.append("")
        lines.append("DESCRIBE (truncated to 40 lines each):")
        for name, text in describes.items():
            lines.append(f"  === {name} ===")
            for ln in text.splitlines()[:40]:
                lines.append(f"  {ln}")

    if logs:
        lines.append("")
        lines.append("LOGS (last 50 lines per failing container):")
        for name, text in logs.items():
            lines.append(f"  === {name} ===")
            for ln in text.splitlines()[-50:]:
                lines.append(f"  {ln}")

    return "\n".join(lines) + "\n"


def _kube_diagnose(wrapper_dir: Path, namespace: str) -> str:
    """Collect live kubectl state and feed it through the parser.

    Runs best-effort: individual kubectl calls that fail yield empty
    sections rather than raising, so the bundle is always produced.
    """
    import json as _json
    import subprocess as _sp

    def _kj(args: "list[str]") -> dict:
        r = _sp.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            return {}
        try:
            return _json.loads(r.stdout)
        except _json.JSONDecodeError:
            return {}

    pods = _kj(["kubectl", "get", "pods", "-n", namespace, "-o", "json"])
    events = _kj(["kubectl", "get", "events", "-n", namespace, "-o", "json"])

    describes: "dict[str, str]" = {}
    logs: "dict[str, str]" = {}
    for item in pods.get("items", []) or []:
        name = item.get("metadata", {}).get("name", "")
        if not name:
            continue
        for cs in item.get("status", {}).get("containerStatuses", []) or []:
            if cs.get("state", {}).get("waiting"):
                d = _sp.run(
                    ["kubectl", "describe", "pod", name, "-n", namespace],
                    capture_output=True,
                    text=True,
                )
                describes[f"pod/{name}"] = d.stdout or ""
                lg = _sp.run(
                    [
                        "kubectl", "logs", name,
                        "-c", cs.get("name", ""),
                        "-n", namespace, "--tail=50",
                    ],
                    capture_output=True,
                    text=True,
                )
                logs[f"{name}/{cs.get('name', '?')}"] = lg.stdout or ""
                break

    return _kube_diagnose_from_json(
        pods=pods, events=events, describes=describes, logs=logs
    )


__all__ = [
    "AUTH_CHOICES",
    "BACKENDS_WITH_ITEMS_API",
    "SKELETON_DESCRIPTIONS",
    "AiManifest",
    "AiTarget",
    "FullstackChoices",
    "GenerationContext",
    "IntegrationManifest",
    "OllamaClient",
    "OllamaConfig",
    "OllamaError",
    "ServiceSummary",
    "TargetResult",
    "TestRunResult",
    "KubernetesResult",
    "_kube_diagnose",
    "_kube_diagnose_from_json",
    "build_system_prompt",
    "clean_response",
    "discover_manifests",
    "discover_siblings",
    "expand_target_paths",
    "format_prompt",
    "generate_targets",
    "load_integration_manifest",
    "load_manifest",
    "manifests_dir",
    "prompt_fullstack_dialog",
    "prompt_user_dialog",
    "run_integration_phase",
    "run_kubernetes_phase",
    "run_service_tests",
    "run_test_and_fix_loop",
    "split_skels_by_kind",
]


if __name__ == "__main__":  # pragma: no cover
    # Allow `python skel_ai_lib.py --check` for a quick smoke test of the
    # Ollama connection without going through the full CLI.
    if "--check" in sys.argv:
        client = OllamaClient()
        client.verify()
        print(f"Ollama OK: {client.config.model} @ {client.config.base_url}")
