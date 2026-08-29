"""나레이션 배속 선택 — 단위 테스트 (2026-08-29).

가장 중요한 건 **1배가 지금과 완전히 같아야 한다**는 것이다. 배속을 고르지 않은
기존 유저의 영상이 조용히 느려지면, 아무도 요청하지 않은 회귀가 전 유저에게 나간다.
그래서 "1배 = tempo 1.4" 를 못 박고, 값을 안 보내는 구버전 FE 도 같은 결과가
나오는지 확인한다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import speeds  # noqa: E402
from services.tts_typecast import MAX_TEMPO, MIN_TEMPO  # noqa: E402


class TestDefaultIsUnchanged(unittest.TestCase):
    """기존 동작 보존 — 이게 깨지면 전 유저의 영상이 바뀐다."""

    def test_one_x_equals_current_tempo(self):
        self.assertEqual(speeds.to_tempo(1.0), 1.4)

    def test_missing_value_equals_current_tempo(self):
        """구버전 FE 는 speed 를 아예 안 보낸다."""
        self.assertEqual(speeds.to_tempo(None), 1.4)

    def test_default_is_one_x(self):
        self.assertEqual(speeds.DEFAULT_SPEED, 1.0)

    def test_base_matches_what_ships_today(self):
        """운영 중인 tempo 와 어긋나면 1배의 의미가 달라진다."""
        self.assertEqual(speeds.BASE_TEMPO, 1.4)


class TestConversion(unittest.TestCase):
    def test_slow(self):
        self.assertAlmostEqual(speeds.to_tempo(0.7), 0.98, places=6)

    def test_fast(self):
        self.assertAlmostEqual(speeds.to_tempo(1.25), 1.75, places=6)

    def test_every_option_within_typecast_range(self):
        """노출하는 배속이 하나라도 범위를 벗어나면 그 선택지는 잘려서 거짓말이 된다."""
        for opt in speeds.SPEEDS:
            tempo = speeds.BASE_TEMPO * opt["value"]
            self.assertGreaterEqual(tempo, MIN_TEMPO, opt)
            self.assertLessEqual(tempo, MAX_TEMPO, opt)

    def test_range_constants_match_tts_module(self):
        self.assertEqual((speeds.MIN_TEMPO, speeds.MAX_TEMPO), (MIN_TEMPO, MAX_TEMPO))


class TestNormalize(unittest.TestCase):
    def test_allowed_values_pass_through(self):
        for v in (0.7, 1.0, 1.25):
            self.assertEqual(speeds.normalize_speed(v), v)

    def test_unknown_values_fall_back(self):
        for bad in (2.0, 0.1, 3, -1, 0, 1.1):
            self.assertEqual(speeds.normalize_speed(bad), 1.0, bad)

    def test_junk_falls_back(self):
        for bad in (None, "1.25", "", [], {}, object()):
            self.assertEqual(speeds.normalize_speed(bad), 1.0, repr(bad))

    def test_booleans_are_not_speeds(self):
        """True 는 int 하위 타입이라 1.0 으로 새어 들어갈 수 있다."""
        self.assertFalse(speeds.is_allowed(True))
        self.assertFalse(speeds.is_allowed(False))

    def test_float_noise_still_matches(self):
        """JSON 왕복으로 미세하게 흔들려도 같은 선택지로 봐야 한다."""
        self.assertEqual(speeds.normalize_speed(0.7000000001), 0.7)

    def test_out_of_range_never_escapes_to_typecast(self):
        """상수를 잘못 고쳐도 API 가 거부할 값이 나가면 안 된다."""
        for bad in (99, -99, "x", None):
            tempo = speeds.to_tempo(bad)
            self.assertGreaterEqual(tempo, MIN_TEMPO)
            self.assertLessEqual(tempo, MAX_TEMPO)


class TestExposedList(unittest.TestCase):
    def test_exactly_one_default(self):
        flags = [s["is_default"] for s in speeds.available_speeds()]
        self.assertEqual(sum(flags), 1)

    def test_default_flag_is_on_one_x(self):
        d = [s for s in speeds.available_speeds() if s["is_default"]][0]
        self.assertEqual(d["value"], 1.0)

    def test_shape_matches_voices_convention(self):
        for s in speeds.available_speeds():
            self.assertEqual(set(s), {"value", "name", "description", "is_default"})

    def test_every_exposed_value_is_allowed(self):
        for s in speeds.available_speeds():
            self.assertTrue(speeds.is_allowed(s["value"]), s)


class TestPreviewCacheKey(unittest.TestCase):
    """배속이 키에 안 들어가면 0.7배를 고르고 1.25배 소리를 듣게 된다."""

    def test_speed_changes_the_key(self):
        from services.voice_preview import _cache_key

        a = _cache_key("tc_x", "같은 문장", speeds.to_tempo(0.7))
        b = _cache_key("tc_x", "같은 문장", speeds.to_tempo(1.25))
        self.assertNotEqual(a, b)

    def test_same_inputs_same_key(self):
        from services.voice_preview import _cache_key

        a = _cache_key("tc_x", "같은 문장", speeds.to_tempo(1.0))
        b = _cache_key("tc_x", "같은 문장", speeds.to_tempo(None))
        self.assertEqual(a, b)

    def test_voice_and_text_still_separate_keys(self):
        from services.voice_preview import _cache_key

        t = speeds.to_tempo(1.0)
        self.assertNotEqual(_cache_key("tc_a", "문장", t), _cache_key("tc_b", "문장", t))
        self.assertNotEqual(_cache_key("tc_a", "문장1", t), _cache_key("tc_a", "문장2", t))


if __name__ == "__main__":
    unittest.main()
