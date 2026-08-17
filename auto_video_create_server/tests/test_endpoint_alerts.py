"""메인 엔드포인트 catch-all 알림 — 단위 테스트 (2026-08-09).

## 이 테스트가 막는 것

`extract_all` / `generate_video` 의 마지막 `except Exception` 이 조용했다.
Typecast·Creatomate 외의 모든 실패(크롤러 파싱 깨짐, LLM 응답 이상, S3 실패 등)가
전부 여기로 흘러와 HTTP 200 으로 나갔다. 그래서:

  - `[ALERT]` 메트릭 필터: 마커가 없어 안 잡힘
  - Lambda Errors 알람: Lambda 는 성공으로 끝나므로 안 잡힘
  - API Gateway 5xx: 200 응답이라 안 잡힘

즉 **완전한 사각지대**였다. 게다가 유저에게는 "다른 글로 시도해주세요"라고
유저 탓처럼 안내됐다.

## 두 방향 모두 고정한다

1. 예상 밖 실패 → 반드시 알림 (사각지대 재발 방지)
2. 유저 탓 실패 → 절대 알림 없음 (오탐으로 알림이 무시되는 것 방지)
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

import api.blog as blog  # noqa: E402
from crawler.dispatcher import UnsupportedPlatformError  # noqa: E402


USER = {"id": "tester"}


def _capture(fn):
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            result = fn()
        except Exception as e:
            result = e
    return result, buf.getvalue()


class TestExtractAllAlerts(unittest.TestCase):
    def _req(self, url="https://blog.naver.com/someone/123"):
        return blog.ExtractMediaRequest(blog_url=url, scene_count=5)

    def test_unexpected_failure_alerts(self):
        """파서가 깨진 경우 — 반드시 알려야 한다."""
        with mock.patch.object(blog, "validate_blog_url", return_value=True), \
             mock.patch.object(
                 blog, "get_blog_media_and_scripts",
                 side_effect=ValueError("본문 영역을 찾을 수 없습니다.")):
            result, out = _capture(lambda: blog.extract_all(self._req(), user=USER))

        self.assertIn("[ALERT]", out)
        self.assertIn("source=extract_all", out)
        self.assertIn("error_type=ValueError", out)
        # 유저에게는 기존 메시지가 그대로 나가야 한다 (동작 변경 없음)
        self.assertEqual(result["error_code"], "crawl_failed")

    def test_alert_carries_host_not_full_url(self):
        """진단에 필요한 건 어느 플랫폼인지 뿐 — 글 주소 전체는 남기지 않는다."""
        url = "https://blog.naver.com/someone/verysecretpost123"
        with mock.patch.object(blog, "validate_blog_url", return_value=True), \
             mock.patch.object(blog, "get_blog_media_and_scripts",
                               side_effect=RuntimeError("boom")):
            _, out = _capture(lambda: blog.extract_all(self._req(url), user=USER))

        self.assertIn("blog_host=blog.naver.com", out)
        self.assertNotIn("verysecretpost123", out)

    def test_unsupported_platform_does_not_alert(self):
        """유저가 지원 안 하는 플랫폼을 넣은 것 — 우리가 할 일이 없다."""
        with mock.patch.object(blog, "validate_blog_url", return_value=True), \
             mock.patch.object(blog, "get_blog_media_and_scripts",
                               side_effect=UnsupportedPlatformError("velog.io")):
            result, out = _capture(lambda: blog.extract_all(self._req(), user=USER))

        self.assertNotIn("[ALERT]", out)
        self.assertEqual(result["error_code"], "unsupported_platform")

    def test_unregistered_blog_does_not_alert(self):
        """등록 안 된 블로그 — 정상적인 거절이다."""
        with mock.patch.object(blog, "validate_blog_url", return_value=False):
            result, out = _capture(lambda: blog.extract_all(self._req(), user=USER))

        self.assertNotIn("[ALERT]", out)
        self.assertEqual(result["error_code"], "blog_not_registered")

    def test_success_does_not_alert(self):
        with mock.patch.object(blog, "validate_blog_url", return_value=True), \
             mock.patch.object(blog, "get_blog_media_and_scripts",
                               return_value={"images": [], "scripts": []}):
            result, out = _capture(lambda: blog.extract_all(self._req(), user=USER))

        self.assertNotIn("[ALERT]", out)
        self.assertEqual(result["status"], "success")


class TestGenerateVideoAlerts(unittest.TestCase):
    def _req(self):
        return blog.GenerateVideoRequest(
            title="테스트",
            scripts=["안녕하세요"],
            sections=[
                blog.SectionMedia(type="image", url="https://example.com/a.jpg")
            ],
            scene_count=5,
        )

    def test_unexpected_failure_alerts(self):
        with mock.patch.object(
            blog, "normalize_scene_count", side_effect=RuntimeError("boom")
        ):
            result, out = _capture(lambda: blog.generate_video(self._req(), user=USER))

        self.assertIn("[ALERT]", out)
        self.assertIn("source=generate_video", out)
        self.assertIn("error_type=RuntimeError", out)
        self.assertEqual(result["status"], "error")

    def test_alert_survives_failure_on_first_line(self):
        """scene_count 할당 줄에서 터져도 알림 코드가 NameError 를 내면 안 된다.

        알림 코드가 2차 사고를 내면 알림 자체를 잃는다.
        """
        with mock.patch.object(
            blog, "normalize_scene_count", side_effect=RuntimeError("boom")
        ):
            result, out = _capture(lambda: blog.generate_video(self._req(), user=USER))

        self.assertNotIsInstance(result, Exception, "except 블록이 예외를 냈다")
        self.assertIn("requested_scene_count=5", out)

    def test_tts_failure_does_not_double_alert(self):
        """TypecastError 는 tts_typecast 안에서 이미 알린다 — 여기서 또 알리면 중복이다."""
        with mock.patch.object(blog, "normalize_scene_count", return_value=5), \
             mock.patch.object(
                 blog, "tts_with_typecast_multi",
                 side_effect=blog.TypecastError("Typecast 401: invalid")):
            result, out = _capture(lambda: blog.generate_video(self._req(), user=USER))

        self.assertEqual(result["error_code"], "tts_failed")
        self.assertNotIn("source=generate_video", out)


if __name__ == "__main__":
    unittest.main()
