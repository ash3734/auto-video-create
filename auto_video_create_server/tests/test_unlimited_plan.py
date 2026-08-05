"""무제한 플랜 — 단위 테스트.

무제한 플랜: `unlimited_start` ~ `unlimited_end` (YYYY-MM-DD, 양끝 포함) 기간에는
크레딧 잔액과 무관하게 생성 가능하고 차감도 하지 않는다. 구독과는 별도 관리.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import account_service as acc  # noqa: E402


def d(offset_days):
    return (datetime.utcnow().date() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


class TestIsUnlimitedActive(unittest.TestCase):

    def test_within_period(self):
        self.assertTrue(acc.is_unlimited_active(
            {"id": "u", "unlimited_start": d(-3), "unlimited_end": d(3)}
        ))

    def test_boundaries_inclusive(self):
        today = d(0)
        self.assertTrue(acc.is_unlimited_active(
            {"id": "u", "unlimited_start": today, "unlimited_end": today}
        ))

    def test_before_start(self):
        self.assertFalse(acc.is_unlimited_active(
            {"id": "u", "unlimited_start": d(1), "unlimited_end": d(10)}
        ))

    def test_after_end(self):
        self.assertFalse(acc.is_unlimited_active(
            {"id": "u", "unlimited_start": d(-10), "unlimited_end": d(-1)}
        ))

    def test_missing_fields(self):
        self.assertFalse(acc.is_unlimited_active({"id": "u"}))
        self.assertFalse(acc.is_unlimited_active({"id": "u", "unlimited_start": d(-1)}))
        self.assertFalse(acc.is_unlimited_active({"id": "u", "unlimited_end": d(1)}))

    def test_malformed_dates_are_not_unlimited(self):
        """형식 오류로 무제한이 열리면 과금 사고 — 반드시 False."""
        for bad in ["2026/01/01", "내일", "", None, 20260101, "2026-13-45"]:
            self.assertFalse(acc.is_unlimited_active(
                {"id": "u", "unlimited_start": bad, "unlimited_end": d(3)}
            ), f"start={bad!r} 이 무제한으로 처리됨")

    def test_non_dict_safe(self):
        self.assertFalse(acc.is_unlimited_active(None))
        self.assertFalse(acc.is_unlimited_active("user"))


class TestCheckUserCredits(unittest.TestCase):
    """무제한이면 잔액 0 이어도 통과, 아니면 기존 규칙."""

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"ENV": "production"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _users(self, user):
        return mock.patch.object(acc, "load_json_from_s3", return_value=[user])

    def test_unlimited_passes_with_zero_credits(self):
        user = {"id": "u", "credits": 0, "unlimited_start": d(-1), "unlimited_end": d(1)}
        with self._users(user):
            self.assertTrue(acc.check_user_credits("u", 1000))

    def test_expired_unlimited_falls_back_to_credits(self):
        user = {"id": "u", "credits": 0, "unlimited_start": d(-10), "unlimited_end": d(-1)}
        with self._users(user):
            self.assertFalse(acc.check_user_credits("u", 1000))

    def test_expired_unlimited_with_enough_credits_passes(self):
        user = {"id": "u", "credits": 5000, "unlimited_start": d(-10), "unlimited_end": d(-1)}
        with self._users(user):
            self.assertTrue(acc.check_user_credits("u", 1000))

    def test_no_unlimited_normal_rules(self):
        with self._users({"id": "u", "credits": 999}):
            self.assertFalse(acc.check_user_credits("u", 1000))
        with self._users({"id": "u", "credits": 1000}):
            self.assertTrue(acc.check_user_credits("u", 1000))


class TestDeductCredits(unittest.TestCase):

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"ENV": "production"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_unlimited_does_not_touch_balance(self):
        user = {"id": "u", "credits": 3000, "unlimited_start": d(-1), "unlimited_end": d(1)}
        with mock.patch.object(acc, "load_json_from_s3", return_value=[user]), \
             mock.patch.object(acc, "save_credit_record") as rec, \
             mock.patch.object(acc, "s3") as s3:
            self.assertTrue(acc.deduct_credits("u", 1000))
            self.assertEqual(user["credits"], 3000, "무제한인데 잔액이 차감됨")
            s3.put_object.assert_not_called()
            # 사용량 추적용 이력은 남긴다
            rec.assert_called_once()
            self.assertEqual(rec.call_args[0][0]["change_type"], "unlimited_use")
            self.assertEqual(rec.call_args[0][0]["amount"], 0)

    def test_history_failure_does_not_block_generation(self):
        user = {"id": "u", "credits": 0, "unlimited_start": d(-1), "unlimited_end": d(1)}
        with mock.patch.object(acc, "load_json_from_s3", return_value=[user]), \
             mock.patch.object(acc, "save_credit_record", side_effect=Exception("S3 다운")), \
             mock.patch.object(acc, "s3"):
            self.assertTrue(acc.deduct_credits("u", 1000))

    def test_normal_user_still_deducted(self):
        user = {"id": "u", "credits": 3000}
        with mock.patch.object(acc, "load_json_from_s3", return_value=[user]), \
             mock.patch.object(acc, "save_credit_record"), \
             mock.patch.object(acc, "s3"):
            self.assertTrue(acc.deduct_credits("u", 1000))
            self.assertEqual(user["credits"], 2000)

    def test_expired_unlimited_insufficient_is_rejected(self):
        user = {"id": "u", "credits": 500, "unlimited_start": d(-9), "unlimited_end": d(-2)}
        with mock.patch.object(acc, "load_json_from_s3", return_value=[user]), \
             mock.patch.object(acc, "save_credit_record"), \
             mock.patch.object(acc, "s3"):
            self.assertFalse(acc.deduct_credits("u", 1000))
            self.assertEqual(user["credits"], 500)


if __name__ == "__main__":
    unittest.main()
