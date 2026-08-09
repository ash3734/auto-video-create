"""장애 알림 마커([ALERT]) — 단위 테스트 (실제 API 호출 없음).

이 테스트가 지키는 것은 두 가지다.

1. 진짜 장애에는 반드시 마커가 붙는다  → 알람이 안 울리는 사고를 막는다
2. 정상 비즈니스 결과에는 절대 안 붙는다 → 오탐으로 알림이 무시되는 사고를 막는다

2번이 특히 중요하다. 오탐이 반복되면 사람이 알림을 안 보게 되고,
그러면 모니터링이 있으나 마나가 된다.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import tts_typecast as tc  # noqa: E402
from services.alerting import ALERT_PREFIX, alert  # noqa: E402


def _capture(fn):
    """fn 을 실행하고 stdout 을 문자열로 돌려준다 (예외는 삼킨다)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            fn()
        except Exception:
            pass
    return buf.getvalue()


def _resp(status=200, content=b"\xff\xfbMP3", body=None):
    r = mock.Mock()
    r.status_code = status
    r.content = content
    r.json.return_value = body if body is not None else {}
    r.text = ""
    return r


class TestAlertFormat(unittest.TestCase):
    def test_prefix_present(self):
        line = alert("creatomate", "무언가 실패")
        self.assertTrue(line.startswith(ALERT_PREFIX))

    def test_metric_filter_pattern_matches(self):
        """CloudWatch 메트릭 필터는 "[ALERT]" 부분 문자열로 매칭한다.

        접두사를 바꾸면 알람이 조용히 죽으므로 여기서 고정한다.
        """
        self.assertEqual(ALERT_PREFIX, "[ALERT]")
        self.assertIn("[ALERT]", alert("x", "y"))

    def test_source_and_env_included(self):
        with mock.patch.dict(os.environ, {"ENV": "production"}):
            line = alert("typecast", "실패")
        self.assertIn("source=typecast", line)
        self.assertIn("env=production", line)

    def test_context_rendered(self):
        line = alert("config", "미등록", scene_count=5, template_id="abc")
        self.assertIn("scene_count=5", line)
        self.assertIn("template_id=abc", line)

    def test_secrets_masked(self):
        line = alert("config", "실패", api_key="sk-real-secret",
                     authorization="Bearer xyz", user_id="linkplc")
        self.assertNotIn("sk-real-secret", line)
        self.assertNotIn("xyz", line)
        self.assertIn("api_key=***", line)
        # 시크릿이 아닌 값은 그대로 보여야 진단이 된다
        self.assertIn("user_id=linkplc", line)

    def test_printed_to_stdout(self):
        out = _capture(lambda: alert("creatomate", "렌더 실패"))
        self.assertIn("[ALERT]", out)


class TestTypecastAlerts(unittest.TestCase):
    """외부 API 실패 → 알림이 울려야 한다."""

    def test_missing_api_key_alerts_as_config(self):
        out = _capture(lambda: tc.tts_with_typecast("안녕", "/tmp/a.mp3", ""))
        self.assertIn("[ALERT]", out)
        self.assertIn("source=config", out)

    def test_auth_failure_alerts_as_config(self):
        """401/402/403 은 재시도로 안 풀린다 — 사람이 콘솔에 가야 한다."""
        for status in (401, 402, 403):
            with mock.patch.object(tc.requests, "post", return_value=_resp(status=status)):
                out = _capture(lambda: tc.tts_with_typecast("안녕", "/tmp/a.mp3", "KEY"))
            self.assertIn("[ALERT]", out, f"status={status} 알림 없음")
            self.assertIn("source=config", out, f"status={status} 분류 오류")

    def test_server_error_alerts_as_typecast(self):
        with mock.patch.object(tc.requests, "post", return_value=_resp(status=500)), \
             mock.patch.object(tc.time, "sleep"):
            out = _capture(lambda: tc.tts_with_typecast("안녕", "/tmp/a.mp3", "KEY"))
        self.assertIn("[ALERT]", out)
        self.assertIn("source=typecast", out)

    def test_api_key_never_appears_in_alert(self):
        with mock.patch.object(tc.requests, "post", return_value=_resp(status=401)):
            out = _capture(lambda: tc.tts_with_typecast("안녕", "/tmp/a.mp3", "SUPER-SECRET-KEY"))
        self.assertNotIn("SUPER-SECRET-KEY", out)

    def test_success_does_not_alert(self):
        with mock.patch.object(tc.requests, "post", return_value=_resp()), \
             mock.patch("builtins.open", mock.mock_open()):
            out = _capture(lambda: tc.tts_with_typecast("안녕", "/tmp/a.mp3", "KEY"))
        self.assertNotIn("[ALERT]", out)


class TestNoFalseAlarms(unittest.TestCase):
    """정상 비즈니스 결과 → 알림이 울리면 안 된다.

    기존 `[!]` 마커는 진짜 장애와 정상 상황을 섞어서 표시하고 있었다.
    그 구분이 [ALERT] 도입의 핵심 이유이므로 회귀를 여기서 막는다.
    """

    def test_empty_script_does_not_alert(self):
        """빈 스크립트는 유저가 채우면 되는 문제 — 사람이 새벽에 깰 일이 아니다."""
        out = _capture(lambda: tc.tts_with_typecast("", "/tmp/a.mp3", "KEY"))
        self.assertNotIn("[ALERT]", out)

    def test_insufficient_credits_does_not_alert(self):
        from services import create_creatomate_video as ccv

        with mock.patch.object(ccv, "check_user_credits", return_value=False), \
             mock.patch.object(ccv, "get_current_credits", return_value=0):
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = ccv.create_creatomate_video([], [], user_id="someone")
        self.assertEqual(result["error"], "insufficient_credits")
        self.assertNotIn("[ALERT]", buf.getvalue())


class TestCreatomateAlerts(unittest.TestCase):
    def _run(self, status, body):
        from services import create_creatomate_video as ccv

        with mock.patch.object(ccv.requests, "post", return_value=_resp(status=status, body=body)):
            buf = io.StringIO()
            with redirect_stdout(buf):
                ccv.create_creatomate_video(["a.mp3"], ["s"], scene_count=5)
        return buf.getvalue()

    def test_missing_template_alerts_as_config(self):
        """2026-08-08 회귀 방지: test 5장면 템플릿이 삭제됐는데 나흘간 아무도 몰랐다."""
        out = self._run(400, {"hint": "No template was found with that ID."})
        self.assertIn("[ALERT]", out)
        self.assertIn("source=config", out)
        self.assertIn("template_id=", out)

    def test_server_error_alerts_as_creatomate(self):
        out = self._run(503, {"message": "service unavailable"})
        self.assertIn("[ALERT]", out)
        self.assertIn("source=creatomate", out)


if __name__ == "__main__":
    unittest.main()
