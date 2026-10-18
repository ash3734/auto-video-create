"""AI 호출 시간 상한 — 단위 테스트 (2026-10-18).

2026-10-18 prod: 대본 생성 OpenAI 호출 하나가 응답 없이 멈춰 람다 60초를 다 쓰고
끊겼다. API Gateway 는 29초에 끊기 때문에 유저는 504 만 받았고, extract-all 의 안내
문구·관리자 알림은 돌지 못했다. SDK 기본값(600초 + 재시도 2회)에 맡기면 안 된다.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import classifier, summarize  # noqa: E402

API_GATEWAY_LIMIT = 29


class TestTimeouts(unittest.TestCase):
    def test_budget_fits_api_gateway(self):
        """분류 + 대본 생성 + 크롤링 여유(약 4초)가 29초 안에 들어가야 실패를 유저에게 돌려줄 수 있다."""
        self.assertLessEqual(classifier.CLASSIFY_TIMEOUT_SECONDS + summarize.LLM_TIMEOUT_SECONDS + 4,
                             API_GATEWAY_LIMIT)

    def test_summarize_openai_client_is_bounded(self):
        import openai
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
             mock.patch.object(openai, "OpenAI") as cli:
            cli.return_value.chat.completions.create.return_value = mock.Mock(
                choices=[mock.Mock(message=mock.Mock(content="{}"))])
            summarize._generate_with_openai("p")
        kw = cli.call_args.kwargs
        self.assertEqual(kw["timeout"], summarize.LLM_TIMEOUT_SECONDS)
        self.assertEqual(kw["max_retries"], 0, "재시도하면 상한이 두 배가 된다")

    def test_classifier_openai_client_is_bounded(self):
        import openai
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
             mock.patch.object(openai, "OpenAI") as cli:
            cli.return_value.chat.completions.create.return_value = mock.Mock(
                choices=[mock.Mock(message=mock.Mock(content="general"))])
            classifier._classify_with_openai("본문")
        kw = cli.call_args.kwargs
        self.assertEqual(kw["timeout"], classifier.CLASSIFY_TIMEOUT_SECONDS)
        self.assertEqual(kw["max_retries"], 0)

    def test_classifier_timeout_falls_back_to_general(self):
        """분류가 시간 초과로 실패해도 대본 생성은 계속돼야 한다."""
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False), \
             mock.patch.object(classifier, "_classify_with_openai", side_effect=TimeoutError("slow")):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            self.assertEqual(classifier.classify_blog("맛집 후기 본문"), "general")


if __name__ == "__main__":
    unittest.main()
