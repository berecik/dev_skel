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

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dev_skel_lib import slugify_service_name


# --------------------------------------------------------------------------- #
#  Configuration & data classes
# --------------------------------------------------------------------------- #


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
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

        ``OLLAMA_BASE_URL`` may be either ``http://host:port`` or
        ``http://host:port/v1`` — the trailing ``/v1`` is normalised away
        because the rest of this module appends the route segments itself.
        """

        base = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
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
        """

        from skel_rag.llm import OllamaError as _NewOllamaError

        try:
            return self.agent.chat(system, user)
        except _NewOllamaError as exc:
            raise OllamaError(str(exc)) from exc


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
    no_input: bool = False,
    allow_no_frontend: bool = True,
    skip_frontend: bool = False,
    allow_no_backend: bool = True,
    skip_backend: bool = False,
) -> FullstackChoices:
    """Run the upgraded interactive dialog and return the choices.

    The dialog walks the user through six logical steps:

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

    print("  Step 1/6: Backend")
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
    print("  Step 2/6: Frontend")
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
    print("  Step 3/6: Service display names")
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
    print("  Step 4/6: Main CRUD entity")
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
    print("  Step 5/6: Authentication style")
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
    print("  Step 6/6: Custom instructions (optional, blank to skip)")
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


def _read_project_yml_minimal(wrapper: Path) -> dict:
    """Tiny hand-rolled parser for ``dev_skel.project.yml``.

    Mirrors ``_bin/skel-deploy._read_project_yml`` so this module does
    not grow a ``pyyaml`` dependency. If the file structure ever
    diverges, keep both parsers in sync.
    """
    yml = wrapper / "dev_skel.project.yml"
    if not yml.is_file():
        raise FileNotFoundError(str(yml))

    data: dict = {"project": {}, "kubernetes": {}, "images": {}, "services": []}
    current_service: "dict | None" = None

    for line in yml.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if line.startswith("  name:"):
            data["project"]["name"] = stripped.split(":", 1)[1].strip()
        elif line.startswith("  cluster:"):
            data["kubernetes"]["cluster"] = stripped.split(":", 1)[1].strip()
        elif line.startswith("  context:"):
            data["kubernetes"]["context"] = stripped.split(":", 1)[1].strip()
        elif line.startswith("  namespace:"):
            data["kubernetes"]["namespace"] = stripped.split(":", 1)[1].strip()
        elif line.startswith("  repository:"):
            data["images"]["repository"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- id:"):
            if current_service:
                data["services"].append(current_service)
            current_service = {"id": stripped.split(":", 1)[1].strip()}
        elif current_service and stripped.startswith("kind:"):
            current_service["kind"] = stripped.split(":", 1)[1].strip()
        elif current_service and stripped.startswith("tech:"):
            current_service["tech"] = stripped.split(":", 1)[1].strip()
        elif current_service and stripped.startswith("port:"):
            current_service["port"] = stripped.split(":", 1)[1].strip()
        elif current_service and stripped.startswith("version:"):
            current_service["version"] = stripped.split(":", 1)[1].strip()

    if current_service:
        data["services"].append(current_service)
    return data


@dataclass
class KubernetesResult:
    """Outcome of :func:`run_kubernetes_phase`."""

    ok: bool
    error: "str | None" = None
    helm_lint_output: str = ""
    generated_files: "list[Path]" = field(default_factory=list)
    failed_resources: "list[str]" = field(default_factory=list)
    fix_iterations: int = 0


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
            project_yml = _read_project_yml_minimal(wrapper_dir)
        except FileNotFoundError as exc:
            return KubernetesResult(ok=False, error=str(exc))

    managed_root = wrapper_dir / "deploy" / "helm" / "templates" / "_managed"
    managed_root.mkdir(parents=True, exist_ok=True)
    for svc in project_yml.get("services", []) or []:
        (managed_root / svc["id"]).mkdir(parents=True, exist_ok=True)

    generated_files: "list[Path]" = []

    if not skip_ai:
        # Tier-2 generation lands in Task 5. Until then, skipping AI is
        # the default behaviour for callers that only want the static
        # shape.
        pass

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
    "_read_project_yml_minimal",
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
