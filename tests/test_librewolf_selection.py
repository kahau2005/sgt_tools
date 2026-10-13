"""Tests for LibreWolf selection in the desktop Check Post and Check Group tools."""

import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from gui.dashboard_window import DashboardWindow
from gui.group_check_window import GroupCheckWindow
from services.link_checker import LibreWolfChecker


class LibreWolfSelectionTests(unittest.TestCase):
    def test_checker_requires_a_selected_folder_without_loading_env(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            with open(os.path.join(temporary_dir, "geckodriver.exe"), "wb"):
                pass
            with patch.object(sys, "_MEIPASS", temporary_dir, create=True):
                with patch(
                    "builtins.open",
                    side_effect=AssertionError("Checker must not read .env"),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "Chưa chọn thư mục LibreWolf"
                    ):
                        LibreWolfChecker(threading.Event())

    def test_checker_resolves_selected_parent_folder(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            version_dir = os.path.join(temporary_dir, "librewolf-version")
            binary = os.path.join(version_dir, "LibreWolf", "librewolf.exe")
            profile = os.path.join(version_dir, "Profiles", "Default")
            os.makedirs(os.path.dirname(binary))
            os.makedirs(profile)
            with open(binary, "wb"):
                pass

            def runtime_defaults(checker):
                checker.geckodriver = "geckodriver.exe"
                checker.page_timeout = checker.CHECK_TIMEOUT_SECONDS
                checker.verdict_timeout = checker.CHECK_TIMEOUT_SECONDS
                checker.binary = None
                checker.profile = None
                checker.headless = False

            with patch.object(
                LibreWolfChecker, "_load_runtime_defaults", runtime_defaults
            ):
                checker = LibreWolfChecker(
                    threading.Event(), librewolf_dir=temporary_dir
                )

            self.assertEqual(checker.binary, os.path.abspath(binary))
            self.assertEqual(checker.profile, os.path.abspath(profile))

    def test_check_post_shows_warning_before_starting_without_folder(self):
        window = DashboardWindow.__new__(DashboardWindow)
        window._librewolf_dir = ""

        with patch("gui.dashboard_window.messagebox.showwarning") as showwarning:
            with patch.object(window, "_check_worker") as worker:
                window._launch_check([], 1, 1)

        showwarning.assert_called_once()
        worker.assert_not_called()

    def test_check_group_shows_warning_when_folder_is_missing(self):
        window = GroupCheckWindow.__new__(GroupCheckWindow)
        window._librewolf_dir = ""

        with patch("gui.group_check_window.messagebox.showwarning") as showwarning:
            allowed = window._require_librewolf_dir()

        self.assertFalse(allowed)
        showwarning.assert_called_once()

    def test_check_group_allows_check_after_folder_is_selected(self):
        window = GroupCheckWindow.__new__(GroupCheckWindow)
        window._librewolf_dir = "C:/LibreWolf"

        with patch("gui.group_check_window.messagebox.showwarning") as showwarning:
            allowed = window._require_librewolf_dir()

        self.assertTrue(allowed)
        showwarning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
