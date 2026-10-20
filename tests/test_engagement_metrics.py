"""Unit tests for Facebook engagement metrics parsing and data models."""

import unittest
from services.link_checker import _parse_engagement_metric, LinkCheckResult
from services.odoo_client import PublishHistory


class EngagementMetricParsingTests(unittest.TestCase):
    def test_parse_simple_integers(self):
        self.assertEqual(_parse_engagement_metric("0"), 0)
        self.assertEqual(_parse_engagement_metric("15"), 15)
        self.assertEqual(_parse_engagement_metric("999"), 999)

    def test_parse_thousands_k(self):
        self.assertEqual(_parse_engagement_metric("1K"), 1000)
        self.assertEqual(_parse_engagement_metric("1.2K"), 1200)
        self.assertEqual(_parse_engagement_metric("1,5k"), 1500)
        self.assertEqual(_parse_engagement_metric("20.5 K"), 20500)

    def test_parse_millions_m(self):
        self.assertEqual(_parse_engagement_metric("1M"), 1000000)
        self.assertEqual(_parse_engagement_metric("2.5m"), 2500000)
        self.assertEqual(_parse_engagement_metric("1,2 M"), 1200000)

    def test_parse_edge_and_empty_values(self):
        self.assertEqual(_parse_engagement_metric(None), 0)
        self.assertEqual(_parse_engagement_metric(""), 0)
        self.assertEqual(_parse_engagement_metric("   "), 0)
        self.assertEqual(_parse_engagement_metric("abc"), 0)
        self.assertEqual(_parse_engagement_metric(-5), 0)

    def test_link_check_result_defaults(self):
        res = LinkCheckResult("alive", "OK")
        self.assertEqual(res.interactions, 0)
        self.assertEqual(res.comments, 0)
        self.assertEqual(res.shares, 0)

    def test_link_check_result_with_metrics(self):
        res = LinkCheckResult("alive", "OK", interactions=25, comments=10, shares=3)
        self.assertEqual(res.interactions, 25)
        self.assertEqual(res.comments, 10)
        self.assertEqual(res.shares, 3)

    def test_publish_history_engagement_fields(self):
        record = PublishHistory(
            id=1,
            posted_at="2026-10-20 10:00:00",
            user_id=1,
            user_name="Tester",
            content_title="Test Post",
            project_id=1,
            project_name="Team A",
            group_link_id=1,
            group_link_name="Group A",
            is_free_group=False,
            free_group_url="",
            external_post_id="123456",
            external_post_url="https://facebook.com/groups/1/posts/123456/",
            status="published",
            detail="OK",
            error_message="",
            interaction_count=50,
            comment_count=12,
            share_count=4,
        )
        self.assertEqual(record.interaction_count, 50)
        self.assertEqual(record.comment_count, 12)
        self.assertEqual(record.share_count, 4)


if __name__ == "__main__":
    unittest.main()
