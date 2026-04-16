from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BIN_DIR = REPO_ROOT / "_bin"

if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))


from dev_skel_lib import generate_project  # noqa: E402


class SkelAddTests(unittest.TestCase):
    def test_dispatches_to_ai_by_default_with_skip_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "_bin"
            bindir.mkdir()
            dispatcher = bindir / "skel-add"
            dispatcher.write_text((BIN_DIR / "skel-add").read_text(encoding="utf-8"), encoding="utf-8")
            dispatcher.chmod(0o755)
            capture = bindir / "skel-gen-ai"
            capture.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "print(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            capture.chmod(0o755)

            result = subprocess.run(
                [sys.executable, str(dispatcher), "demo", "python-fastapi-skel", "Ticket API"],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            result.stdout.strip(),
            '["--skip-base", "demo", "python-fastapi-skel", "Ticket API"]',
        )

    def test_dispatches_to_static_with_existing_project_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "_bin"
            bindir.mkdir()
            dispatcher = bindir / "skel-add"
            dispatcher.write_text((BIN_DIR / "skel-add").read_text(encoding="utf-8"), encoding="utf-8")
            dispatcher.chmod(0o755)
            capture = bindir / "skel-gen-static"
            capture.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "print(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            capture.chmod(0o755)

            result = subprocess.run(
                [
                    sys.executable,
                    str(dispatcher),
                    "--static",
                    "demo",
                    "python-fastapi-skel",
                    "Ticket API",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            result.stdout.strip(),
            '["--existing-project", "demo", "python-fastapi-skel", "Ticket API"]',
        )

    def test_generate_project_requires_existing_wrapper_in_add_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skel = root / "_skels" / "demo-skel"
            skel.mkdir(parents=True)
            gen = skel / "gen"
            gen.write_text("#!/bin/sh\nmkdir -p \"$1/$2\"\n", encoding="utf-8")
            gen.chmod(0o755)

            with self.assertRaises(SystemExit) as ctx:
                generate_project(
                    root=root,
                    skel_name="demo-skel",
                    proj_name="wrapper",
                    service_name="Ticket API",
                    existing_project=True,
                )

        self.assertIn("existing project directory not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
