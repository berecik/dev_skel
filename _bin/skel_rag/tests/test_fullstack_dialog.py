"""Unit tests for ``skel_ai_lib.prompt_fullstack_dialog`` defaults.

Covers the invariants set by the user in 2026-04:

  1. Backend default still resolves to the first backend that ships
     the wrapper-shared items API contract.
  2. Frontend default is now ``ts-react-skel`` (was list[0]).
  3. ``skip_backend=True`` produces a frontend-only project — the
     resulting ``FullstackChoices.has_backend`` is False and the
     backend service label / extra prompts are blank.
  4. Skipping both backend AND frontend raises ``SystemExit`` so we
     never produce an empty wrapper.

All cases run in ``no_input=True`` mode so no TTY is required.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_bin"))

import skel_ai_lib  # noqa: E402  (path setup precedes the import)


BACKENDS = [
    "java-spring-skel",
    "python-django-bolt-skel",
    "python-fastapi-skel",
    "rust-actix-skel",
]
FRONTENDS = ["flutter-skel", "ts-react-skel"]


def _dialog(**overrides):
    base = dict(
        available_backends=BACKENDS,
        available_frontends=FRONTENDS,
        default_project_name="myproj",
        no_input=True,
    )
    base.update(overrides)
    return skel_ai_lib.prompt_fullstack_dialog(**base)


class FullstackDialogDefaultsTests(unittest.TestCase):
    def test_backend_default_picks_items_api_backend(self) -> None:
        choices = _dialog()
        self.assertTrue(choices.has_backend)
        # Both django-bolt and fastapi are in BACKENDS_WITH_ITEMS_API;
        # the picker should land on whichever sorts first in the list.
        self.assertIn(
            choices.backend_skeleton,
            skel_ai_lib.BACKENDS_WITH_ITEMS_API,
        )

    def test_frontend_default_is_ts_react_skel(self) -> None:
        choices = _dialog()
        self.assertTrue(choices.has_frontend)
        self.assertEqual(
            choices.frontend_skeleton,
            "ts-react-skel",
            msg=(
                "Frontend default must resolve to ts-react-skel even "
                "when another frontend (e.g. flutter-skel) sorts ahead "
                "of it."
            ),
        )

    def test_frontend_default_falls_back_when_react_absent(self) -> None:
        choices = _dialog(available_frontends=["flutter-skel"])
        self.assertEqual(choices.frontend_skeleton, "flutter-skel")

    def test_skip_backend_is_frontend_only(self) -> None:
        choices = _dialog(skip_backend=True)
        self.assertFalse(choices.has_backend)
        self.assertIsNone(choices.backend_skeleton)
        self.assertIsNone(choices.backend_service_label)
        self.assertEqual(choices.backend_extra, "")
        # Integration prompt is meaningless without a backend.
        self.assertEqual(choices.integration_extra, "")
        # Frontend default must still be respected.
        self.assertTrue(choices.has_frontend)
        self.assertEqual(choices.frontend_skeleton, "ts-react-skel")

    def test_skip_frontend_is_backend_only(self) -> None:
        choices = _dialog(skip_frontend=True)
        self.assertTrue(choices.has_backend)
        self.assertFalse(choices.has_frontend)
        self.assertIsNone(choices.frontend_skeleton)
        self.assertEqual(choices.frontend_extra, "")
        self.assertEqual(choices.integration_extra, "")

    def test_skip_both_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            _dialog(skip_backend=True, skip_frontend=True)


if __name__ == "__main__":
    unittest.main()
