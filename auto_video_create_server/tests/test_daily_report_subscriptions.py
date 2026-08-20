"""일일 리포트의 구독 현황 블록 — 단위 테스트 (AWS 호출 없음).

리포트는 매일 자동으로 나가고 아무도 검산하지 않는다. 조용히 틀린 숫자를 보내는 게
가장 나쁜 실패이므로 경계 조건을 못 박는다.

특히 `can_create` 를 고정한다 — 구독이 살아 있어도 크레딧이 0이고 무제한이 아니면
2026-08-17 차감 버그 수정 이후로는 **진입 자체가 막힌다**. 돈은 내고 있는데 못 쓰는
유저를 리포트가 놓치면 알 방법이 없다.
"""
import io
import json
import os
import sys
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import daily_report as dr  # noqa: E402

TODAY = date(2026, 8, 20)


def _user(uid, sub_end, credits=None, u_start=None, u_end=None):
    u = {"id": uid, "subscription_end": sub_end}
    if credits is not None:
        u["credits"] = credits
    if u_start:
        u["unlimited_start"] = u_start
    if u_end:
        u["unlimited_end"] = u_end
    return u


def _s3_with(users):
    s3 = mock.Mock()
    s3.get_object.return_value = {
        "Body": io.BytesIO(json.dumps(users).encode("utf-8"))
    }
    return s3


def _status(users, today=TODAY):
    # is_unlimited_active 는 UTC 오늘을 보므로 테스트 기준일과 맞춘다
    with mock.patch("services.account_service.datetime") as m:
        m.utcnow.return_value = mock.Mock(**{"date.return_value": today})
        m.strptime = __import__("datetime").datetime.strptime
        return dr.subscription_status(today=today, s3=_s3_with(users))


class TestWhoCounts(unittest.TestCase):
    def test_expired_excluded(self):
        rows = _status([_user("old", "2026-08-19", credits=5000)])
        self.assertEqual(rows, [])

    def test_expiring_today_included(self):
        """만료일 당일은 아직 구독자다 (양끝 포함 정책)."""
        rows = _status([_user("today", "2026-08-20", credits=5000)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["days_left"], 0)

    def test_missing_date_excluded(self):
        for bad in (None, "", "언젠가", "2026/08/30"):
            rows = _status([_user("bad", bad, credits=5000)])
            self.assertEqual(rows, [], repr(bad))

    def test_sorted_by_urgency(self):
        rows = _status([
            _user("far", "2027-01-01", credits=5000),
            _user("soon", "2026-08-25", credits=5000),
            _user("mid", "2026-09-30", credits=5000),
        ])
        self.assertEqual([r["user_id"] for r in rows], ["soon", "mid", "far"])


class TestCanCreate(unittest.TestCase):
    def test_zero_credits_cannot_create(self):
        """muk_soul 실제 사례 — 구독은 살아 있는데 크레딧이 0이라 진입이 막힌다."""
        rows = _status([_user("muk_soul", "2099-09-09", credits=0)])
        self.assertFalse(rows[0]["can_create"])

    def test_missing_credits_field_cannot_create(self):
        """woorim 실제 사례 — credits 필드 자체가 없다."""
        rows = _status([_user("woorim", "2026-12-31")])
        self.assertFalse(rows[0]["can_create"])
        self.assertEqual(rows[0]["credits"], 0)

    def test_below_one_video_cannot_create(self):
        rows = _status([_user("almost", "2026-12-31", credits=999)])
        self.assertFalse(rows[0]["can_create"])

    def test_exactly_one_video_can_create(self):
        rows = _status([_user("ok", "2026-12-31", credits=1000)])
        self.assertTrue(rows[0]["can_create"])

    def test_unlimited_can_create_with_zero_credits(self):
        rows = _status([_user("linkplc", "2026-09-07", credits=0,
                              u_start="2026-08-05", u_end="2026-09-07")])
        self.assertTrue(rows[0]["can_create"])
        self.assertTrue(rows[0]["unlimited"])

    def test_expired_unlimited_falls_back_to_credits(self):
        rows = _status([_user("past", "2026-12-31", credits=0,
                              u_start="2026-07-01", u_end="2026-08-01")])
        self.assertFalse(rows[0]["unlimited"])
        self.assertFalse(rows[0]["can_create"])


class TestFormatting(unittest.TestCase):
    def test_perpetual_shown_as_muggihan(self):
        """2099 같은 값에 '26,682일 남음'을 찍으면 정보가 아니라 소음이다."""
        rows = _status([_user("test", "2099-12-31", credits=1000)])
        out = "\n".join(dr.format_subscriptions(rows))
        self.assertIn("무기한", out)
        self.assertNotIn("일 남음", out.split("test")[1].split("\n")[0])

    def test_expiry_warning_marked(self):
        rows = _status([_user("soon", "2026-08-25", credits=5000)])
        out = "\n".join(dr.format_subscriptions(rows))
        self.assertIn("만료 임박", out)

    def test_perpetual_not_marked_as_expiring(self):
        rows = _status([_user("forever", "2099-12-31", credits=5000)])
        out = "\n".join(dr.format_subscriptions(rows))
        self.assertNotIn("만료 임박", out)

    def test_blocked_user_flagged(self):
        rows = _status([_user("muk_soul", "2099-09-09", credits=0)])
        out = "\n".join(dr.format_subscriptions(rows))
        self.assertIn("생성 불가", out)

    def test_healthy_user_has_no_warning(self):
        rows = _status([_user("fine", "2027-06-01", credits=9000)])
        out = "\n".join(dr.format_subscriptions(rows))
        self.assertNotIn("⚠", out)

    def test_no_subscribers_message(self):
        out = "\n".join(dr.format_subscriptions([]))
        self.assertIn("구독 중인 유저가 없습니다", out)

    def test_fetch_failure_is_explicit(self):
        """조용히 빈 목록을 보내면 '구독자가 없다'로 오해된다."""
        out = "\n".join(dr.format_subscriptions(None))
        self.assertIn("불러오지 못했습니다", out)


class TestResilience(unittest.TestCase):
    def test_s3_failure_returns_none_not_raise(self):
        s3 = mock.Mock()
        s3.get_object.side_effect = RuntimeError("S3 다운")
        self.assertIsNone(dr.subscription_status(today=TODAY, s3=s3))

    def test_report_still_sent_when_subscriptions_fail(self):
        """구독 조회가 실패해도 사용량 리포트는 나가야 한다."""
        body = dr.format_report(TODAY, {"alice": 2}, {"alice": 2}, subscriptions=None)
        self.assertIn("총 시도 2회", body)
        self.assertIn("불러오지 못했습니다", body)

    def test_subscriptions_appear_in_full_report(self):
        rows = _status([_user("linkplc", "2026-09-07", credits=0,
                              u_start="2026-08-05", u_end="2026-09-07")])
        body = dr.format_report(TODAY, {}, {}, subscriptions=rows)
        self.assertIn("구독 현황", body)
        self.assertIn("linkplc", body)
        self.assertIn("무제한", body)


if __name__ == "__main__":
    unittest.main()
