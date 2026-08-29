"""보이지 않는 문자로 채워진 스크립트 — 회귀 테스트 (2026-08-29).

## 무엇을 막는가

prod 에서 유저 auctionrun0643 이 8장면으로 만들 때, 블로그 본문이 모자라 요약 모델이
7·8번 스크립트를 **제로폭 공백(U+200B) 하나**로 채웠다.

화면에서는 빈 칸으로 보이고 `.strip()` 검사도 통과한다 — 파이썬은 제로폭 공백을
공백으로 보지 않는다. 그래서 그대로 Typecast 로 나가 422 로 거절당했고, 유저는
영어 API 에러를 보며 **9분간 9번 재시도**하고 영상을 한 편도 못 만들었다.

핵심은 "빈 문자열" 이 아니라 **"눈에 안 보이는데 길이는 있는 문자열"** 을 잡는 것이다.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services.tts_typecast import (  # noqa: E402
    TypecastError,
    clean_for_speech,
    tts_with_typecast,
    tts_with_typecast_multi,
)

ZWSP = "​"


class TestStripWouldHaveMissedIt(unittest.TestCase):
    """이 전제가 깨지면 이 버그의 설명 자체가 달라진다."""

    def test_python_strip_does_not_remove_zero_width_space(self):
        self.assertEqual(ZWSP.strip(), ZWSP)
        self.assertTrue(bool(ZWSP.strip()))

    def test_clean_for_speech_does(self):
        self.assertEqual(clean_for_speech(ZWSP), "")


class TestCleanForSpeech(unittest.TestCase):
    def test_invisible_only_becomes_empty(self):
        for ch in ("​", "‌", "‍", "﻿", "⁠", "­"):
            self.assertEqual(clean_for_speech(ch), "", repr(ch))

    def test_real_text_survives_untouched(self):
        s = "일산요진와이시티 84타입 아파트경매 분석"
        self.assertEqual(clean_for_speech(s), s)

    def test_invisible_removed_from_middle(self):
        """네이버 본문에는 문장 중간에도 제로폭 공백이 흔하다."""
        self.assertEqual(clean_for_speech(f"경매{ZWSP}분석"), "경매분석")

    def test_newlines_become_spaces(self):
        self.assertEqual(clean_for_speech("첫 줄\n둘째 줄"), "첫 줄 둘째 줄")

    def test_whitespace_collapsed_and_trimmed(self):
        self.assertEqual(clean_for_speech("  경매   분석  "), "경매 분석")

    def test_whitespace_only_is_empty(self):
        for s in ("", "   ", "\n\t", None, 123, [], f" {ZWSP} "):
            self.assertEqual(clean_for_speech(s), "", repr(s))

    def test_punctuation_and_digits_kept(self):
        self.assertEqual(clean_for_speech("2025타경61113 사건!"), "2025타경61113 사건!")

    def test_emoji_kept(self):
        """이모지는 보이는 문자다 — 지우면 안 된다 (Typecast 가 판단할 몫)."""
        self.assertEqual(clean_for_speech("낙찰 🎉"), "낙찰 🎉")


class TestSingleCallGuard(unittest.TestCase):
    def test_zero_width_rejected_before_network(self):
        """네트워크로 나가기 전에 막아야 한다 — 나가면 영어 422 를 받는다."""
        with mock.patch("services.tts_typecast.requests.post") as post:
            with self.assertRaises(TypecastError) as ctx:
                tts_with_typecast(ZWSP, "/tmp/x.mp3", "KEY")
        post.assert_not_called()
        self.assertIn("비어 있어", str(ctx.exception))


class TestMultiReportsEveryBlank(unittest.TestCase):
    def _scripts(self):
        return [
            "신축 아파트 경매, 안양의 신규 주거 공간 소개!",
            "주거 환경과 규모, 내부 면적 구성 확인해보세요.",
            "힐스테이트인덕원역베르텍스의 감정가와 정보 공개!",
            "안전하고 쾌적한 단지 환경과 진입로 소개합니다.",
            "경매 임대차 관계와 점유 현황에 대한 분석",
            "교통 요충지의 미래 가치와 지리적 입지 여건 파악",
            ZWSP,
            ZWSP,
        ]

    def test_real_prod_case_is_rejected(self):
        with mock.patch("services.tts_typecast.requests.post") as post:
            with self.assertRaises(TypecastError) as ctx:
                tts_with_typecast_multi(self._scripts(), "KEY")
        post.assert_not_called()
        self.assertIn("7번", str(ctx.exception))
        self.assertIn("8번", str(ctx.exception))

    def test_message_tells_the_way_out(self):
        with mock.patch("services.tts_typecast.requests.post"):
            with self.assertRaises(TypecastError) as ctx:
                tts_with_typecast_multi(self._scripts(), "KEY")
        msg = str(ctx.exception)
        self.assertIn("채우", msg)
        self.assertIn("장면 수", msg)

    def test_all_blanks_listed_not_just_the_first(self):
        """하나씩 알려주면 채우고 다시 눌렀다가 또 막힌다."""
        with mock.patch("services.tts_typecast.requests.post"):
            with self.assertRaises(TypecastError) as ctx:
                tts_with_typecast_multi(["ok", ZWSP, "ok", "   ", "ok"], "KEY")
        msg = str(ctx.exception)
        self.assertIn("2번", msg)
        self.assertIn("4번", msg)

    def test_dict_form_scripts_also_checked(self):
        with mock.patch("services.tts_typecast.requests.post"):
            with self.assertRaises(TypecastError) as ctx:
                tts_with_typecast_multi([{"script": "ok"}, {"script": ZWSP}], "KEY")
        self.assertIn("2번", str(ctx.exception))

    def test_healthy_scripts_pass_the_guard(self):
        """정상 스크립트가 이 검사에 걸리면 전 유저가 영상을 못 만든다."""
        calls = []

        def fake(text, output_path, api_key, **kw):
            calls.append(text)
            return output_path, None

        with mock.patch("services.tts_typecast.tts_with_typecast", side_effect=fake), \
             mock.patch("services.tts_typecast.upload_to_s3", return_value="https://x/y.mp3"), \
             mock.patch("services.tts_typecast.os.makedirs"):
            paths, urls = tts_with_typecast_multi(self._scripts()[:6], "KEY")
        self.assertEqual(len(urls), 6)
        self.assertEqual(len(calls), 6)


class TestNoAlertForUserInput(unittest.TestCase):
    """빈 스크립트는 장애가 아니라 입력 문제다 — 알람을 울리면 안 된다."""

    def test_blank_script_does_not_alert(self):
        with mock.patch("services.tts_typecast.alert") as alert_fn, \
             mock.patch("services.tts_typecast.requests.post"):
            with self.assertRaises(TypecastError):
                tts_with_typecast_multi(["ok", ZWSP], "KEY")
        alert_fn.assert_not_called()

    def test_missing_api_key_still_alerts(self):
        """설정 오류는 반대로 반드시 알려야 한다 — 가드가 이걸 가리면 안 된다."""
        with mock.patch("services.tts_typecast.alert") as alert_fn:
            with self.assertRaises(TypecastError):
                tts_with_typecast("정상 문장", "/tmp/x.mp3", None)
        alert_fn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
