from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


from dev_skel_backport import main  # noqa: E402


class BackportRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        (self.root / "_bin").mkdir()
        (self.root / "_skels").mkdir()
        (self.root / "_test_projects").mkdir()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _write_sidecar(self, service_dir: Path, rel: str) -> None:
        (service_dir / ".skel_context.json").write_text(
            json.dumps({"skeleton_path_rel": rel}) + "\n",
            encoding="utf-8",
        )

    def test_propose_collects_same_relative_changed_files(self) -> None:
        skeleton = self.root / "_skels" / "go-skel"
        (skeleton / "internal").mkdir(parents=True)
        (skeleton / "internal" / "config.go").write_text("old\n", encoding="utf-8")

        wrapper = self.root / "_test_projects" / "demo"
        service = wrapper / "ticket_api"
        (service / "internal").mkdir(parents=True)
        (service / "internal" / "config.go").write_text("new\n", encoding="utf-8")
        self._write_sidecar(service, "../../_skels/go-skel")

        stderr = io.StringIO()
        rc = main(["propose", str(service)], cwd=self.root, progress=stderr)
        self.assertEqual(rc, 0)
        self.assertIn("propose internal/config.go", stderr.getvalue())

        artifacts = sorted((self.root / ".ai" / "backport").glob("*/result.json"))
        self.assertEqual(len(artifacts), 1)
        payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["candidates"][0]["rel_path"], "internal/config.go")

    def test_apply_writes_back_to_skeleton(self) -> None:
        skeleton = self.root / "_skels" / "go-skel"
        (skeleton / "internal").mkdir(parents=True)
        target = skeleton / "internal" / "handlers.go"
        target.write_text("before\n", encoding="utf-8")

        wrapper = self.root / "_test_projects" / "demo"
        service = wrapper / "ticket_api"
        (service / "internal").mkdir(parents=True)
        (service / "internal" / "handlers.go").write_text("after\n", encoding="utf-8")
        self._write_sidecar(service, "../../_skels/go-skel")

        stderr = io.StringIO()
        rc = main(["apply", str(service)], cwd=self.root, progress=stderr)
        self.assertEqual(rc, 0)
        self.assertEqual(target.read_text(encoding="utf-8"), "after\n")

    def test_generate_uses_test_projects_workspace(self) -> None:
        gen_calls: list[tuple[Path, str, str, str | None]] = []

        import dev_skel_backport as runtime
        original_generate_project = runtime.generate_project

        def _fake_generate_project(root: Path, skel: str, proj: str, service_name: str | None = None) -> str:
            gen_calls.append((root, skel, proj, service_name))
            out = Path.cwd() / proj / "service"
            out.mkdir(parents=True, exist_ok=True)
            return "service"

        runtime.generate_project = _fake_generate_project
        try:
            stderr = io.StringIO()
            rc = main(["generate", "go-skel", "--service-name", "Ticket API"], cwd=self.root, progress=stderr)
        finally:
            runtime.generate_project = original_generate_project

        self.assertEqual(rc, 0)
        self.assertEqual(gen_calls[0][1], "go-skel")
        self.assertEqual(gen_calls[0][2], "backport-go")
        self.assertEqual(gen_calls[0][3], "Ticket API")


if __name__ == "__main__":
    unittest.main()
