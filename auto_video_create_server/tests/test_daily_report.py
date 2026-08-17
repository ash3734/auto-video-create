"""일일 사용량 리포트 — 단위 테스트 (AWS 호출 없음, boto3 mock).

집계 자체보다 **경계 조건**을 주로 고정한다. 리포트는 매일 자동으로 나가고 아무도
검산하지 않으므로, 조용히 틀린 숫자를 보내는 게 가장 나쁜 실패다.
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import daily_report as dr  # noqa: E402


def _rec(user, ts, reason="video_generation"):
    return {"user_id": user, "timestamp": ts, "change_type": "deduct",
            "amount": -1000, "reason": reason}


class FakeS3:
    """list_objects_v2 페이지네이터와 get_object 만 흉내낸다."""

    def __init__(self, objects):
        self._objects = objects  # {key: record dict}

    def get_paginator(self, _name):
        outer = self

        class P:
            def paginate(self, **kwargs):
                prefix = kwargs.get("Prefix", "")
                yield {"Contents": [{"Key": k} for k in outer._objects if k.startswith(prefix)]}

        return P()

    def get_object(self, Bucket, Key):  # noqa: N803
        import io, json
        return {"Body": io.BytesIO(json.dumps(self._objects[Key]).encode())}


class TestKstDayBounds(unittest.TestCase):
    def test_kst_day_maps_to_utc_window(self):
        """KST 하루는 UTC 로 전날 15:00 ~ 당일 15:00 이다."""
        start, end = dr.kst_day_bounds(date(2026, 8, 17))
        self.assertEqual(start, datetime(2026, 8, 16, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc))


class TestCountSuccesses(unittest.TestCase):
    def test_counts_only_video_generation(self):
        """관리자 충전(admin_add)은 사용량이 아니다."""
        s3 = FakeS3({
            "credits/alice/20260817_010000.json": _rec("alice", "2026-08-17T01:00:00"),
            "credits/alice/20260817_020000.json": _rec("alice", "2026-08-17T02:00:00", reason="admin_add"),
        })
        self.assertEqual(dr.count_successes(date(2026, 8, 17), s3=s3), {"alice": 1})

    def test_kst_boundary_included_and_excluded(self):
        """UTC 로 저장되므로 KST 하루 경계가 정확해야 한다.

        KST 8/17 = UTC 8/16 15:00 ~ 8/17 15:00.
        """
        s3 = FakeS3({
            # UTC 8/16 15:00 = KST 8/17 00:00 → 포함
            "credits/alice/20260816_150000.json": _rec("alice", "2026-08-16T15:00:00"),
            # UTC 8/16 14:59 = KST 8/16 23:59 → 제외 (전날)
            "credits/bob/20260816_145900.json": _rec("bob", "2026-08-16T14:59:00"),
            # UTC 8/17 15:00 = KST 8/18 00:00 → 제외 (다음날)
            "credits/carol/20260817_150000.json": _rec("carol", "2026-08-17T15:00:00"),
        })
        self.assertEqual(dr.count_successes(date(2026, 8, 17), s3=s3), {"alice": 1})

    def test_unreadable_record_does_not_break_report(self):
        s3 = FakeS3({"credits/alice/20260817_010000.json": _rec("alice", "2026-08-17T01:00:00")})
        orig = s3.get_object
        calls = {"n": 0}

        def flaky(**kwargs):
            calls["n"] += 1
            raise RuntimeError("S3 다운")

        s3.get_object = flaky
        self.assertEqual(dr.count_successes(date(2026, 8, 17), s3=s3), {})
        self.assertEqual(calls["n"], 1)
        s3.get_object = orig

    def test_empty_day(self):
        self.assertEqual(dr.count_successes(date(2026, 8, 17), s3=FakeS3({})), {})


class TestCountAttempts(unittest.TestCase):
    def _logs(self, messages, fail=False):
        m = mock.Mock()
        if fail:
            m.filter_log_events.side_effect = RuntimeError("권한 없음")
        else:
            m.filter_log_events.return_value = {
                "events": [{"message": msg} for msg in messages]
            }
        return m

    def test_parses_user_id(self):
        logs = self._logs([
            "generate_video 호출 user_id=alice",
            "generate_video 호출 user_id=alice",
            "generate_video 호출 user_id=bob",
        ])
        self.assertEqual(dr.count_attempts(date(2026, 8, 17), "/lg", logs=logs),
                         {"alice": 2, "bob": 1})

    def test_log_failure_returns_none_not_crash(self):
        """로그를 못 읽어도 성공 수만이라도 보내야 한다."""
        logs = self._logs([], fail=True)
        self.assertIsNone(dr.count_attempts(date(2026, 8, 17), "/lg", logs=logs))

    def test_pattern_matches_actual_log_line(self):
        """api/blog.py 의 진입 로그 형식과 짝이다 — 바뀌면 집계가 조용히 0 이 된다."""
        line = "generate_video 호출 user_id=linkplc"
        self.assertIn(dr.ATTEMPT_PATTERN, line)
        self.assertEqual(dr.ATTEMPT_RE.search(line).group(1), "linkplc")


class TestFormatReport(unittest.TestCase):
    def test_zero_day_still_reports(self):
        """0건인 날도 내용이 있어야 한다 — 메일이 안 오면 고장과 구분이 안 된다."""
        body = dr.format_report(date(2026, 8, 17), {}, {})
        self.assertIn("2026-08-17", body)
        self.assertIn("실행한 유저가 없습니다", body)

    def test_shows_attempts_successes_failures(self):
        body = dr.format_report(date(2026, 8, 17), {"alice": 5}, {"alice": 3})
        self.assertIn("총 시도 5회 / 성공 3회 / 실패 2회", body)
        self.assertIn("실패 2", body)

    def test_user_with_only_attempts_appears(self):
        """전부 실패한 유저가 리포트에서 빠지면 안 된다 — 가장 중요한 신호다."""
        body = dr.format_report(date(2026, 8, 17), {"bob": 3}, {})
        self.assertIn("bob", body)
        self.assertIn("시도 3회 / 성공 0회", body)

    def test_attempts_unavailable_degrades_gracefully(self):
        body = dr.format_report(date(2026, 8, 17), None, {"alice": 2})
        self.assertIn("시도 수는 로그 조회 실패로 생략", body)
        self.assertIn("alice", body)


class TestSendDailyReport(unittest.TestCase):
    def test_publishes_to_sns(self):
        sns = mock.Mock()
        with mock.patch.object(dr, "build_daily_report",
                               return_value=(date(2026, 8, 17), "본문")):
            dr.send_daily_report(topic_arn="arn:test", sns=sns)
        sns.publish.assert_called_once()
        kw = sns.publish.call_args.kwargs
        self.assertEqual(kw["TopicArn"], "arn:test")
        self.assertIn("2026-08-17", kw["Subject"])

    def test_no_topic_does_not_crash(self):
        with mock.patch.object(dr, "build_daily_report",
                               return_value=(date(2026, 8, 17), "본문")), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REPORT_TOPIC_ARN", None)
            body = dr.send_daily_report()
        self.assertEqual(body, "본문")

    def test_defaults_to_yesterday_kst(self):
        captured = {}

        def fake_counts(target_date, **kwargs):
            captured["date"] = target_date
            return {}

        with mock.patch.object(dr, "count_successes", side_effect=fake_counts), \
             mock.patch.object(dr, "count_attempts", return_value={}):
            dr.build_daily_report()

        expected = (datetime.now(dr.KST) - timedelta(days=1)).date()
        self.assertEqual(captured["date"], expected)


if __name__ == "__main__":
    unittest.main()
