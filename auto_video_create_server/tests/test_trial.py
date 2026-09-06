"""공개 체험 계정 — 단위 테스트 (2026-08-30).

랜딩에서 test 계정의 아이디·비밀번호를 공개한다(PO 결정). 그래서 두 가지를 못 박는다.

1. **prod 에서는 절대 로그인되지 않는다.**
   users.json 을 test·prod 가 공유하고 로그인이 ENV 를 구분하지 않으므로, 막지 않으면
   비밀번호 공개가 곧 prod 개방이 된다. 워터마크 없는 영상이 나가고 크레딧도 실제로 빠진다.

2. **IP 당 하루 3회.**
   Creatomate·Typecast·OpenAI 키를 test 와 prod 가 공유한다. 체험이 몰리면 그 달
   prod 고객이 영상을 못 만든다.
"""
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import trial  # noqa: E402


class _Req:
    def __init__(self, ip=None, headers=None):
        self.headers = headers or ({"x-forwarded-for": ip} if ip else {})
        self.client = None


class TestProdBlock(unittest.TestCase):
    def test_blocked_on_prod(self):
        with mock.patch.dict(os.environ, {"ENV": "production"}, clear=False):
            self.assertTrue(trial.blocked_on_prod("test"))

    def test_allowed_on_test(self):
        with mock.patch.dict(os.environ, {"ENV": "test"}, clear=False):
            self.assertFalse(trial.blocked_on_prod("test"))

    def test_missing_env_treated_as_prod(self):
        """ENV 가 없거나 오타면 안전한 쪽(prod)으로 본다."""
        for env in ("", "prod", "PRODUCTION", "tset", "staging"):
            with mock.patch.dict(os.environ, {"ENV": env}, clear=False):
                self.assertTrue(trial.blocked_on_prod("test"), env)

    def test_real_customers_never_blocked(self):
        """실수로 유료 고객을 막으면 서비스가 멈춘다."""
        with mock.patch.dict(os.environ, {"ENV": "production"}, clear=False):
            for uid in ("auctionrun0643", "linkplc", "ssonek", "woorim", "테스트", "", None):
                self.assertFalse(trial.blocked_on_prod(uid), repr(uid))


class TestClientIp(unittest.TestCase):
    def test_takes_first_forwarded_address(self):
        """API Gateway 를 거치면 XFF 에 여러 개가 붙는다. 원 클라이언트는 첫 번째다."""
        r = _Req(headers={"x-forwarded-for": "1.2.3.4, 70.41.3.18, 150.172.238.178"})
        self.assertEqual(trial.client_ip(r), "1.2.3.4")

    def test_single_address(self):
        self.assertEqual(trial.client_ip(_Req("203.0.113.9")), "203.0.113.9")

    def test_missing_header_does_not_raise(self):
        self.assertIsInstance(trial.client_ip(_Req()), str)


class TestDailyLimit(unittest.TestCase):
    def setUp(self):
        self.store = {}

        def fake_load(day):
            return json.loads(self.store[day]) if day in self.store else {}

        def fake_save(day, data):
            self.store[day] = json.dumps(data)

        self.load = mock.patch.object(trial, "_load", side_effect=fake_load)
        self.save = mock.patch.object(trial, "_save", side_effect=fake_save)
        self.load.start(); self.save.start()
        self.addCleanup(self.load.stop); self.addCleanup(self.save.stop)

    def test_three_allowed_fourth_blocked(self):
        ip = "1.1.1.1"
        for i in range(1, 4):
            got = trial.check_and_count(ip)
            self.assertTrue(got["allowed"], i)
            self.assertEqual(got["used"], i)
        self.assertFalse(trial.check_and_count(ip)["allowed"])

    def test_limit_is_three(self):
        self.assertEqual(trial.DAILY_LIMIT_PER_IP, 3)

    def test_different_ips_counted_separately(self):
        for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
            for _ in range(3):
                self.assertTrue(trial.check_and_count(ip)["allowed"])
        # 각자 3회씩 썼어도 서로에게 영향이 없다
        self.assertFalse(trial.check_and_count("1.1.1.1")["allowed"])
        self.assertFalse(trial.check_and_count("2.2.2.2")["allowed"])

    def test_raw_ip_is_not_stored(self):
        """원본 IP 를 보관할 이유가 없다."""
        trial.check_and_count("203.0.113.77")
        blob = "".join(self.store.values())
        self.assertNotIn("203.0.113.77", blob)

    def test_counting_failure_allows_use(self):
        """카운터가 깨졌다고 체험을 막으면, 손해는 써보러 온 사람이 본다."""
        with mock.patch.object(trial, "_load", side_effect=RuntimeError("S3 다운")):
            got = trial.check_and_count("9.9.9.9")
        self.assertTrue(got["allowed"])


class TestDailyTotalAlert(unittest.TestCase):
    def setUp(self):
        self.store = {}
        mock.patch.object(trial, "_load",
                          side_effect=lambda d: json.loads(self.store[d]) if d in self.store else {}).start()
        mock.patch.object(trial, "_save",
                          side_effect=lambda d, x: self.store.__setitem__(d, json.dumps(x))).start()
        self.addCleanup(mock.patch.stopall)

    def _use(self, n):
        """서로 다른 IP 로 n 회 사용 (IP 당 3회 제한을 피하려고 IP 를 바꾼다)."""
        for i in range(n):
            trial.check_and_count(f"10.0.0.{i}")

    def test_alerts_when_daily_total_exceeds(self):
        with mock.patch.object(trial, "alert") as a:
            self._use(trial.DAILY_TOTAL_ALERT)
        a.assert_called_once()
        self.assertEqual(a.call_args.args[0], "trial")

    def test_does_not_alert_below_threshold(self):
        with mock.patch.object(trial, "alert") as a:
            self._use(trial.DAILY_TOTAL_ALERT - 1)
        a.assert_not_called()

    def test_alerts_only_once_per_day(self):
        """매 요청마다 울리면 소음이 되어 진짜 알림을 무시하게 된다."""
        with mock.patch.object(trial, "alert") as a:
            self._use(trial.DAILY_TOTAL_ALERT + 8)
        self.assertEqual(a.call_count, 1)

    def test_alert_carries_numbers_not_ips(self):
        with mock.patch.object(trial, "alert") as a:
            self._use(trial.DAILY_TOTAL_ALERT)
        kwargs = a.call_args.kwargs
        self.assertIn("daily_total", kwargs)
        self.assertIn("unique_ips", kwargs)
        self.assertNotIn("ip", kwargs)


if __name__ == "__main__":
    unittest.main()
