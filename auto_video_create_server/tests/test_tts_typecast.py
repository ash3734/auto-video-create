"""Typecast TTS — 단위 테스트 (실제 API 호출 없음, requests mock)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import tts_typecast as tc  # noqa: E402


def _resp(status=200, content=b"\xff\xfbMP3", body=None):
    r = mock.Mock()
    r.status_code = status
    r.content = content
    r.json.return_value = body if body is not None else {}
    r.text = ""
    return r


class TestPayload(unittest.TestCase):

    def _capture(self, **kwargs):
        with mock.patch.object(tc.requests, "post", return_value=_resp()) as post, \
             mock.patch("builtins.open", mock.mock_open()):
            tc.tts_with_typecast("안녕하세요", "/tmp/a.mp3", "KEY", **kwargs)
        return post.call_args

    def test_endpoint_and_auth_header(self):
        args = self._capture()
        self.assertEqual(args[0][0], "https://api.typecast.ai/v1/text-to-speech")
        self.assertEqual(args.kwargs["headers"]["X-API-KEY"], "KEY")

    def test_default_voice_and_model(self):
        payload = self._capture().kwargs["json"]
        self.assertEqual(payload["voice_id"], "tc_62e8f21e979b3860fe2f6a24")
        self.assertEqual(payload["model"], "ssfm-v30")
        self.assertEqual(payload["language"], "kor")

    def test_mp3_output_requested(self):
        payload = self._capture().kwargs["json"]
        self.assertEqual(payload["output"]["audio_format"], "mp3")

    def test_speed_maps_to_audio_tempo(self):
        payload = self._capture(speed=1.4).kwargs["json"]
        self.assertEqual(payload["output"]["audio_tempo"], 1.4)

    def test_voice_id_override(self):
        payload = self._capture(voice_id="uc_custom").kwargs["json"]
        self.assertEqual(payload["voice_id"], "uc_custom")

    def test_timeout_is_set(self):
        """호출이 무한정 붙잡히면 Lambda 30초 예산을 통째로 날린다."""
        self.assertIsNotNone(self._capture().kwargs.get("timeout"))


class TestTempoClamp(unittest.TestCase):

    def test_within_range(self):
        self.assertEqual(tc._clamp_tempo(1.4), 1.4)

    def test_clamped_to_bounds(self):
        self.assertEqual(tc._clamp_tempo(5.0), tc.MAX_TEMPO)
        self.assertEqual(tc._clamp_tempo(0.1), tc.MIN_TEMPO)

    def test_garbage_falls_back_to_1(self):
        for bad in [None, "빠르게", [], {}]:
            self.assertEqual(tc._clamp_tempo(bad), 1.0)


class TestValidation(unittest.TestCase):

    def test_missing_api_key(self):
        with self.assertRaises(tc.TypecastError) as cm:
            tc.tts_with_typecast("안녕", "/tmp/a.mp3", "")
        self.assertIn("TYPECAST_API_KEY", str(cm.exception))

    def test_empty_text_rejected_before_request(self):
        """빈 스크립트는 422 를 부르고 장면↔오디오 인덱스를 깨뜨리므로 미리 막는다."""
        with mock.patch.object(tc.requests, "post") as post:
            for blank in ["", "   ", None]:
                with self.assertRaises(tc.TypecastError):
                    tc.tts_with_typecast(blank, "/tmp/a.mp3", "KEY")
            post.assert_not_called()

    def test_long_text_truncated(self):
        long_text = "가" * 3000
        with mock.patch.object(tc.requests, "post", return_value=_resp()) as post, \
             mock.patch("builtins.open", mock.mock_open()):
            tc.tts_with_typecast(long_text, "/tmp/a.mp3", "KEY")
        self.assertEqual(len(post.call_args.kwargs["json"]["text"]), tc.MAX_TEXT_LENGTH)


class TestErrorHandling(unittest.TestCase):

    def test_402_raises_without_retry(self):
        """결제 오류는 재시도해도 소용없다 (Supertone 사고 때 실제로 겪은 상태)."""
        resp = _resp(402, body={"message": "Payment Required"})
        with mock.patch.object(tc.requests, "post", return_value=resp) as post:
            with self.assertRaises(tc.TypecastError) as cm:
                tc.tts_with_typecast("안녕", "/tmp/a.mp3", "KEY")
        self.assertEqual(post.call_count, 1)
        self.assertIn("402", str(cm.exception))

    def test_429_retries_once(self):
        with mock.patch.object(tc.requests, "post",
                               side_effect=[_resp(429), _resp(200)]) as post, \
             mock.patch.object(tc.time, "sleep"), \
             mock.patch("builtins.open", mock.mock_open()):
            path, _ = tc.tts_with_typecast("안녕", "/tmp/a.mp3", "KEY")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(path, "/tmp/a.mp3")

    def test_retry_gives_up_after_second_failure(self):
        with mock.patch.object(tc.requests, "post",
                               side_effect=[_resp(503), _resp(503)]) as post, \
             mock.patch.object(tc.time, "sleep"):
            with self.assertRaises(tc.TypecastError):
                tc.tts_with_typecast("안녕", "/tmp/a.mp3", "KEY")
        self.assertEqual(post.call_count, 2)

    def test_network_error_retried_then_raised(self):
        import requests as rq
        with mock.patch.object(tc.requests, "post",
                               side_effect=rq.RequestException("timeout")) as post, \
             mock.patch.object(tc.time, "sleep"):
            with self.assertRaises(tc.TypecastError):
                tc.tts_with_typecast("안녕", "/tmp/a.mp3", "KEY")
        self.assertEqual(post.call_count, 2)

    def test_api_key_never_in_error_message(self):
        resp = _resp(401, body={"detail": "invalid key"})
        with mock.patch.object(tc.requests, "post", return_value=resp):
            with self.assertRaises(tc.TypecastError) as cm:
                tc.tts_with_typecast("안녕", "/tmp/a.mp3", "SUPERSECRETKEY")
        self.assertNotIn("SUPERSECRETKEY", str(cm.exception))


class TestMulti(unittest.TestCase):

    def test_generates_and_uploads_each_script(self):
        scripts = [{"script": "하나"}, {"script": "둘"}, "셋"]
        with mock.patch.object(tc, "tts_with_typecast",
                               side_effect=lambda t, p, *a, **k: (p, None)) as gen, \
             mock.patch.object(tc, "upload_to_s3",
                               side_effect=lambda p, b, k: f"https://{b}.s3.amazonaws.com/{k}"), \
             mock.patch.object(tc.os, "makedirs"):
            paths, urls = tc.tts_with_typecast_multi(scripts, "KEY")
        self.assertEqual(len(paths), 3)
        self.assertEqual(len(urls), 3)
        self.assertEqual(gen.call_count, 3)
        # dict / 문자열 스크립트 모두 텍스트로 추출돼야 한다
        self.assertEqual([c[0][0] for c in gen.call_args_list], ["하나", "둘", "셋"])

    def test_urls_are_unique_per_clip(self):
        scripts = [{"script": f"s{i}"} for i in range(5)]
        with mock.patch.object(tc, "tts_with_typecast",
                               side_effect=lambda t, p, *a, **k: (p, None)), \
             mock.patch.object(tc, "upload_to_s3",
                               side_effect=lambda p, b, k: f"https://{b}.s3.amazonaws.com/{k}"), \
             mock.patch.object(tc.os, "makedirs"):
            _, urls = tc.tts_with_typecast_multi(scripts, "KEY")
        self.assertEqual(len(set(urls)), 5, "S3 키가 겹치면 이전 클립을 덮어쓴다")


if __name__ == "__main__":
    unittest.main()
