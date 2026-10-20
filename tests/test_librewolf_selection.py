"""Tests for LibreWolf selection in the desktop Check Post and Check Group tools."""

import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from gui.dashboard_window import DashboardWindow
from gui.group_check_window import GroupCheckWindow
from services.link_checker import LibreWolfChecker, LinkCheckResult
from services.odoo_client import PublishHistory


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

    def _create_dummy_record(self, record_id: int, post_url: str) -> PublishHistory:
        return PublishHistory(
            id=record_id,
            posted_at="2026-04-01 10:00:00",
            user_id=1,
            user_name="Tester",
            content_title="Test",
            project_id=1,
            project_name="Project",
            group_link_id=1,
            group_link_name="Group",
            is_free_group=False,
            free_group_url="",
            external_post_id=str(record_id),
            external_post_url=post_url,
            status="published",
            detail="",
            error_message="",
        )

    def test_recheck_failed_picks_both_timeout_and_error(self):
        window = DashboardWindow.__new__(DashboardWindow)
        window._check_thread = None
        window.status_var = MagicMock()
        window._launch_check = MagicMock()
        window.tree = MagicMock()

        rec_alive = self._create_dummy_record(1, "https://facebook.com/groups/1/posts/100")
        rec_timeout = self._create_dummy_record(2, "https://facebook.com/groups/1/posts/200")
        rec_error = self._create_dummy_record(3, "https://facebook.com/groups/1/posts/300")

        window._filtered_rows = [rec_alive, rec_timeout, rec_error]
        window._last_results = {
            1: LinkCheckResult("alive", "OK"),
            2: LinkCheckResult("error", "TIMEOUT_KHONG_XAC_DINH"),
            3: LinkCheckResult("error", "CHECK_WORKER_ERROR: Driver crashed"),
        }
        window.tree.exists.return_value = False

        window._recheck_failed()

        window._launch_check.assert_called_once()
        passed_records = window._launch_check.call_args[0][0]
        self.assertEqual([r.id for r in passed_records], [2, 3])

    def test_recheck_failed_when_no_failed_records(self):
        window = DashboardWindow.__new__(DashboardWindow)
        window._check_thread = None
        window.status_var = MagicMock()
        window._launch_check = MagicMock()
        window.tree = MagicMock()

        rec_alive = self._create_dummy_record(1, "https://facebook.com/groups/1/posts/100")
        window._filtered_rows = [rec_alive]
        window._last_results = {1: LinkCheckResult("alive", "OK")}
        window.tree.exists.return_value = False

        window._recheck_failed()

        window._launch_check.assert_not_called()
        window.status_var.set.assert_called_with(
            "Không có dòng lỗi hoặc timeout cần check lại."
        )

    def test_recheck_timeouts_alias_exists(self):
        window = DashboardWindow.__new__(DashboardWindow)
        self.assertEqual(window._recheck_timeouts, window._recheck_failed)


if __name__ == "__main__":
    unittest.main()
