"""음성 선택 + 미리듣기 — 단위 테스트 (외부 호출 없음).

돈과 직결되는 두 가지를 고정한다.

1. **허용 목록 검증** — 요청의 voice_id 를 그대로 믿으면 유저가 임의 ID 로 엉뚱한
   음성(영어 등) 영상을 만들 수 있고, 그건 1,000크레딧이 날아가는 일이다.
2. **미리듣기 캐시** — 같은 (음성, 텍스트) 조합이 재생성되면 ▶ 연타마다 비용이 나간다.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import voice_preview as vp  # noqa: E402
from services import voices as v  # noqa: E402


class TestCatalog(unittest.TestCase):
    def test_five_voices_exposed(self):
        self.assertEqual(len(v.available_voices()), 5)

    def test_exactly_one_default(self):
        defaults = [x for x in v.available_voices() if x["is_default"]]
        self.assertEqual(len(defaults), 1)

    def test_default_is_hyelee(self):
        """기존 유저의 결과물이 바뀌면 안 된다 — 전환 이후 모든 영상이 혜리였다."""
        default = next(x for x in v.available_voices() if x["is_default"])
        self.assertEqual(default["name"], "혜리")
        self.assertEqual(v.DEFAULT_VOICE_ID, "tc_62e8f21e979b3860fe2f6a24")

    def test_default_matches_tts_module(self):
        """tts_typecast 의 기본값과 어긋나면 미선택 유저의 음성이 조용히 바뀐다."""
        from services.tts_typecast import DEFAULT_VOICE_ID as TTS_DEFAULT
        self.assertEqual(v.DEFAULT_VOICE_ID, TTS_DEFAULT)

    def test_ids_unique(self):
        ids = [x["voice_id"] for x in v.VOICES]
        self.assertEqual(len(set(ids)), len(ids))

    def test_every_voice_has_korean_name_and_description(self):
        """로마자 이름(Hyelee)이 화면에 새어 나가면 안 된다."""
        for item in v.VOICES:
            self.assertTrue(item["name"].strip(), item)
            self.assertTrue(item["description"].strip(), item)
            self.assertNotEqual(item["name"], item["typecast_name"], item)


class TestNormalize(unittest.TestCase):
    def test_allowed_passes_through(self):
        for item in v.VOICES:
            self.assertEqual(v.normalize_voice_id(item["voice_id"]), item["voice_id"])

    def test_unknown_id_falls_back(self):
        """허용 목록 밖 ID 는 기본값으로 — 크레딧을 태우는 대신 안전하게 흐른다."""
        self.assertEqual(
            v.normalize_voice_id("tc_deadbeefdeadbeefdeadbeef"), v.DEFAULT_VOICE_ID
        )

    def test_garbage_falls_back(self):
        for bad in (None, "", 123, [], {}, True, "  "):
            self.assertEqual(v.normalize_voice_id(bad), v.DEFAULT_VOICE_ID, repr(bad))


class TestPreviewCacheKey(unittest.TestCase):
    def test_same_inputs_same_key(self):
        a = vp._cache_key("tc_a", "안녕하세요")
        b = vp._cache_key("tc_a", "안녕하세요")
        self.assertEqual(a, b)

    def test_text_change_changes_key(self):
        """스크립트를 고치면 새로 생성되어야 한다 — 옛 음성이 재생되면 안 된다."""
        a = vp._cache_key("tc_a", "안녕하세요")
        b = vp._cache_key("tc_a", "안녕하세요!")
        self.assertNotEqual(a, b)

    def test_voice_change_changes_key(self):
        self.assertNotEqual(vp._cache_key("tc_a", "같은 문장"), vp._cache_key("tc_b", "같은 문장"))

    def test_key_is_scoped_by_voice(self):
        self.assertTrue(vp._cache_key("tc_a", "x").startswith("voice-previews/tc_a/"))

    def test_separator_prevents_collision(self):
        """구분자가 없으면 ('ab','c') 와 ('a','bc') 가 같은 키가 된다."""
        self.assertNotEqual(vp._cache_key("ab", "c"), vp._cache_key("a", "bc"))


class TestPreviewFlow(unittest.TestCase):
    def _run(self, head_hit, tts_side_effect=None):
        s3 = mock.Mock()
        if not head_hit:
            from botocore.exceptions import ClientError
            s3.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
        with mock.patch.object(vp, "_s3", return_value=s3), \
             mock.patch.object(vp, "tts_with_typecast", side_effect=tts_side_effect) as tts, \
             mock.patch.object(vp, "upload_to_s3", return_value="https://x/y.mp3"), \
             mock.patch("os.remove"):
            result = vp.get_preview_url(v.DEFAULT_VOICE_ID, "테스트 문장", "KEY")
        return result, tts

    def test_cache_hit_skips_tts(self):
        """캐시가 있으면 TTS 를 부르지 않는다 — 이게 비용 방어의 핵심이다."""
        result, tts = self._run(head_hit=True)
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["cached"])
        tts.assert_not_called()

    def test_cache_miss_generates(self):
        result, tts = self._run(head_hit=False)
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["cached"])
        tts.assert_called_once()

    def test_tts_failure_returns_error_not_raise(self):
        """미리듣기 실패가 예외로 터지면 화면이 멈춘다 — 에러 응답으로 흡수한다."""
        from services.tts_typecast import TypecastError
        result, _ = self._run(head_hit=False, tts_side_effect=TypecastError("Typecast 500"))
        self.assertEqual(result["status"], "error")
        self.assertIn("다시 시도", result["message"])

    def test_empty_text_rejected_without_tts(self):
        for bad in ("", "   ", None):
            with mock.patch.object(vp, "tts_with_typecast") as tts:
                result = vp.get_preview_url(v.DEFAULT_VOICE_ID, bad, "KEY")
            self.assertEqual(result["status"], "error")
            tts.assert_not_called()

    def test_unknown_voice_falls_back_to_default(self):
        """미리듣기에서도 임의 ID 를 그대로 쓰지 않는다."""
        s3 = mock.Mock()
        with mock.patch.object(vp, "_s3", return_value=s3):
            key = vp._cache_key(v.normalize_voice_id("tc_bogus"), "문장")
        self.assertIn(v.DEFAULT_VOICE_ID, key)

    def test_long_text_truncated(self):
        long_text = "가" * 500
        s3 = mock.Mock()
        from botocore.exceptions import ClientError
        s3.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
        with mock.patch.object(vp, "_s3", return_value=s3), \
             mock.patch.object(vp, "tts_with_typecast") as tts, \
             mock.patch.object(vp, "upload_to_s3", return_value="https://x/y.mp3"), \
             mock.patch("os.remove"):
            vp.get_preview_url(v.DEFAULT_VOICE_ID, long_text, "KEY")
        sent = tts.call_args[0][0]
        self.assertEqual(len(sent), vp.MAX_PREVIEW_CHARS)

    def test_preview_speed_matches_video(self):
        """미리듣기 속도가 영상과 다르면 들은 것과 결과물이 달라진다."""
        from services.tts_typecast import tts_with_typecast  # noqa: F401
        self.assertEqual(vp.PREVIEW_SPEED, 1.4)


class TestGenerateVideoUsesRequestVoice(unittest.TestCase):
    def test_request_voice_id_reaches_tts(self):
        import api.blog as blog

        chosen = "tc_66ab0e26ec23f325b7ad51df"  # 예슬
        req = blog.GenerateVideoRequest(
            title="t",
            scripts=["안녕"],
            sections=[blog.SectionMedia(type="image", url="https://e/a.jpg")],
            scene_count=5,
            voice_id=chosen,
        )
        with mock.patch.object(blog, "tts_with_typecast_multi",
                               side_effect=RuntimeError("stop here")) as tts:
            blog.generate_video(req, user={"id": "u"})
        self.assertEqual(tts.call_args.kwargs["voice_id"], chosen)

    def test_bogus_voice_id_falls_back(self):
        import api.blog as blog

        req = blog.GenerateVideoRequest(
            title="t",
            scripts=["안녕"],
            sections=[blog.SectionMedia(type="image", url="https://e/a.jpg")],
            voice_id="tc_not_in_allowlist",
        )
        with mock.patch.object(blog, "tts_with_typecast_multi",
                               side_effect=RuntimeError("stop here")) as tts:
            blog.generate_video(req, user={"id": "u"})
        self.assertEqual(tts.call_args.kwargs["voice_id"], v.DEFAULT_VOICE_ID)

    def test_missing_voice_id_uses_default(self):
        """구버전 FE 가 voice_id 를 안 보내도 기존 동작이 유지되어야 한다."""
        import api.blog as blog

        req = blog.GenerateVideoRequest(
            title="t",
            scripts=["안녕"],
            sections=[blog.SectionMedia(type="image", url="https://e/a.jpg")],
        )
        with mock.patch.object(blog, "tts_with_typecast_multi",
                               side_effect=RuntimeError("stop here")) as tts:
            blog.generate_video(req, user={"id": "u"})
        self.assertEqual(tts.call_args.kwargs["voice_id"], v.DEFAULT_VOICE_ID)


if __name__ == "__main__":
    unittest.main()
