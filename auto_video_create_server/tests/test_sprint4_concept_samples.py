"""
test_sprint4_concept_samples.py — sprint-4 (B-2) 단위 테스트

컨셉 영상 샘플 4종 + 가변 스크립트/장면 수(N) 관련 순수 로직 검증.
외부 의존성(S3, Creatomate, Claude/OpenAI API) 없이 mock 으로 대체.
pytest 없이 stdlib unittest 사용 (기존 test_cycle3_subtitle.py 관행 재사용).
"""

import copy
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# 서버 루트를 sys.path 에 추가
_SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_ROOT not in sys.path:
    sys.path.insert(0, _SERVER_ROOT)

# create_creatomate_video.py 는 모듈 임포트 시점에 CREATOMATE_API_KEY 를 읽는다 —
# 테스트 환경에 없으면 값 없이도 임포트는 되도록 placeholder 를 미리 세팅.
os.environ.setdefault("CREATOMATE_API_KEY", "test-dummy-key")


# ─────────────────────────────────────────────
# concept_samples 테스트
# ─────────────────────────────────────────────

class TestConceptSamples(unittest.TestCase):

    def test_four_samples_defined(self):
        from services.concept_samples import SAMPLE_DEFINITIONS
        self.assertEqual(
            set(SAMPLE_DEFINITIONS.keys()),
            {"sample_1", "sample_2", "sample_3", "sample_4"},
        )

    def test_exactly_one_default_sample(self):
        from services.concept_samples import SAMPLE_DEFINITIONS
        defaults = [s for s in SAMPLE_DEFINITIONS.values() if s["is_default"]]
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0]["concept_sample_id"], "sample_1")

    def test_scene_count_placeholder_values(self):
        """api-contract.md / data-model.md placeholder 값(s1=4/s2=6/s3=5/s4=4)과 정합."""
        from services.concept_samples import SAMPLE_DEFINITIONS
        expected = {"sample_1": 4, "sample_2": 6, "sample_3": 5, "sample_4": 4}
        for sid, scene_count in expected.items():
            self.assertEqual(SAMPLE_DEFINITIONS[sid]["scene_count"], scene_count)

    def test_get_sample_known_id(self):
        from services.concept_samples import get_sample
        sample = get_sample("sample_2")
        self.assertEqual(sample["concept_sample_id"], "sample_2")
        self.assertEqual(sample["scene_count"], 6)

    def test_get_sample_unknown_id_falls_back_to_default(self):
        """미인식 값이면 sample_1 로 폴백 (api-contract.md '미선택 통과 허용')."""
        from services.concept_samples import get_sample, DEFAULT_SAMPLE_ID
        sample = get_sample("does_not_exist")
        self.assertEqual(sample["concept_sample_id"], DEFAULT_SAMPLE_ID)

    def test_get_sample_none_falls_back_to_default(self):
        from services.concept_samples import get_sample, DEFAULT_SAMPLE_ID
        sample = get_sample(None)
        self.assertEqual(sample["concept_sample_id"], DEFAULT_SAMPLE_ID)

    def test_get_scene_count_helper(self):
        from services.concept_samples import get_scene_count
        self.assertEqual(get_scene_count("sample_3"), 5)
        self.assertEqual(get_scene_count(None), 4)  # sample_1 폴백

    def test_get_template_id_placeholder_is_none(self):
        """전 샘플 template_id 가 placeholder(None) 상태 — DEP-S4-01 미해소."""
        from services.concept_samples import get_template_id
        for sid in ("sample_1", "sample_2", "sample_3", "sample_4"):
            self.assertIsNone(get_template_id(sid, "test"))
            self.assertIsNone(get_template_id(sid, "production"))

    def test_get_template_id_env_key_normalization(self):
        """env 값이 'production'(대소문자 무관) 이 아니면 전부 'test' 키로 취급."""
        from services.concept_samples import get_template_id
        # 값 자체는 placeholder(None)이라 결과는 같지만, KeyError 없이 안전하게 처리되는지 확인
        self.assertIsNone(get_template_id("sample_1", None))
        self.assertIsNone(get_template_id("sample_1", ""))
        self.assertIsNone(get_template_id("sample_1", "PRODUCTION"))
        self.assertIsNone(get_template_id("sample_1", "staging"))

    def test_list_samples_public_excludes_internal_fields(self):
        """BE 내부 전용 필드(creatomate_template_id/subtitle_element_suffixes/hook_prompt) 비노출."""
        from services.concept_samples import list_samples_public
        samples = list_samples_public()
        self.assertEqual(len(samples), 4)
        expected_keys = {
            "concept_sample_id", "name", "is_default",
            "scene_count", "hero_still_url", "sample_video_url",
        }
        for s in samples:
            self.assertEqual(set(s.keys()), expected_keys)
            self.assertNotIn("creatomate_template_id", s)
            self.assertNotIn("subtitle_element_suffixes", s)
            self.assertNotIn("hook_prompt", s)

    def test_list_samples_public_order_and_names(self):
        from services.concept_samples import list_samples_public
        samples = list_samples_public()
        names = {s["concept_sample_id"]: s["name"] for s in samples}
        self.assertEqual(names["sample_1"], "컨셉 1")
        self.assertEqual(names["sample_2"], "컨셉 2")
        self.assertEqual(names["sample_3"], "컨셉 3")
        self.assertEqual(names["sample_4"], "컨셉 4")


# ─────────────────────────────────────────────
# summarize.py — scene_count 가변화 테스트
# ─────────────────────────────────────────────

class TestBuildShortsOutputSchema(unittest.TestCase):

    def test_min_max_items_match_scene_count(self):
        from services.summarize import build_shorts_output_schema
        schema = build_shorts_output_schema(6)
        self.assertEqual(schema["properties"]["scripts"]["minItems"], 6)
        self.assertEqual(schema["properties"]["scripts"]["maxItems"], 6)

    def test_does_not_mutate_module_constant(self):
        """deepcopy 미적용 회귀 방지 — 원본 SHORTS_OUTPUT_SCHEMA 에 minItems 가 새지 않아야 함."""
        from services.summarize import build_shorts_output_schema, SHORTS_OUTPUT_SCHEMA
        build_shorts_output_schema(4)
        build_shorts_output_schema(6)
        self.assertNotIn("minItems", SHORTS_OUTPUT_SCHEMA["properties"]["scripts"])
        self.assertNotIn("maxItems", SHORTS_OUTPUT_SCHEMA["properties"]["scripts"])


class TestNormalizeScripts(unittest.TestCase):
    """architecture.md §3-4 — "6개면 인덱스4 제거" 특수분기 제거 + 일반 패딩/절단."""

    def test_exact_length_untouched(self):
        from services.summarize import _normalize_scripts
        scripts = [{"script": f"s{i}"} for i in range(5)]
        result = _normalize_scripts(list(scripts), 5)
        self.assertEqual(result, scripts)

    def test_pads_when_short(self):
        from services.summarize import _normalize_scripts
        scripts = [{"script": "a"}, {"script": "b"}]
        result = _normalize_scripts(scripts, 5)
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], {"script": "a"})
        self.assertEqual(result[-1], {"script": ""})

    def test_truncates_when_long(self):
        from services.summarize import _normalize_scripts
        scripts = [{"script": f"s{i}"} for i in range(8)]
        result = _normalize_scripts(scripts, 5)
        self.assertEqual(len(result), 5)
        self.assertEqual(result, [{"script": f"s{i}"} for i in range(5)])

    def test_six_is_not_special_cased_when_scene_count_is_six(self):
        """N=6 일 때 6개 응답은 정상값 — 과거처럼 인덱스4 를 제거하면 안 됨."""
        from services.summarize import _normalize_scripts
        scripts = [{"script": f"s{i}"} for i in range(6)]
        result = _normalize_scripts(list(scripts), 6)
        self.assertEqual(result, scripts)
        self.assertEqual(len(result), 6)

    def test_six_truncated_to_five_when_scene_count_is_five(self):
        from services.summarize import _normalize_scripts
        scripts = [{"script": f"s{i}"} for i in range(6)]
        result = _normalize_scripts(scripts, 5)
        self.assertEqual(len(result), 5)
        self.assertEqual(result, [{"script": f"s{i}"} for i in range(5)])


class TestSummarizeForShortsSetsPromptFormatting(unittest.TestCase):
    """프롬프트 템플릿에 scene_count/hook_prompt 가 정상적으로 주입되는지 (format 에러 없이)."""

    def test_restaurant_prompt_formats_without_error(self):
        from services.summarize import RESTAURANT_PROMPT
        prompt = RESTAURANT_PROMPT.format(text="본문", scene_count=6, hook_prompt="훅 지침")
        self.assertIn("6개", prompt)
        self.assertIn("훅 지침", prompt)

    def test_general_prompt_formats_without_error(self):
        from services.summarize import GENERAL_PROMPT
        prompt = GENERAL_PROMPT.format(text="본문", scene_count=4, hook_prompt="훅 지침2")
        self.assertIn("4개", prompt)
        self.assertIn("훅 지침2", prompt)

    def test_summarize_uses_scene_count_and_hook_prompt_with_claude_path(self):
        """ANTHROPIC_API_KEY 존재 시 Claude 경로 호출 + scene_count/hook_prompt 가 프롬프트에 반영."""
        from services import summarize

        captured = {}

        def fake_generate_with_claude(prompt, schema):
            captured["prompt"] = prompt
            captured["schema"] = schema
            return '{"title": "t", "scripts": [{"script": "a"}, {"script": "b"}]}'

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy"}):
            with patch.object(summarize, "_generate_with_claude", side_effect=fake_generate_with_claude):
                title, scripts = summarize.summarize_for_shorts_sets(
                    "블로그 본문", category="restaurant", scene_count=4, hook_prompt="특별 훅 지침"
                )

        self.assertEqual(title, "t")
        self.assertEqual(len(scripts), 4)  # 2개 응답 → 4개로 패딩
        self.assertIn("특별 훅 지침", captured["prompt"])
        self.assertEqual(captured["schema"]["properties"]["scripts"]["minItems"], 4)
        self.assertEqual(captured["schema"]["properties"]["scripts"]["maxItems"], 4)


# ─────────────────────────────────────────────
# create_creatomate_video.py — concept_sample_id 게이팅 테스트
# ─────────────────────────────────────────────

class TestCreateCreatomateVideoTemplateGating(unittest.TestCase):
    """architecture.md §4-2 — template_id 미확보(placeholder) 시 방어적 에러 반환."""

    def test_unconfigured_sample_returns_error_without_calling_api(self):
        from services import create_creatomate_video as ccv

        with patch.object(ccv, "requests") as mock_requests:
            result = ccv.create_creatomate_video(
                audio_paths=["a.mp3", "b.mp3"],
                scripts=[{"script": "a"}, {"script": "b"}],
                concept_sample_id="sample_1",  # placeholder → template_id=None
                title="제목",
                user_id=None,
            )
            self.assertEqual(result.get("error"), "concept_sample_template_not_configured")
            mock_requests.post.assert_not_called()

    def test_unknown_concept_sample_id_falls_back_to_default_and_still_unconfigured(self):
        from services import create_creatomate_video as ccv

        with patch.object(ccv, "requests") as mock_requests:
            result = ccv.create_creatomate_video(
                audio_paths=["a.mp3"],
                scripts=[{"script": "a"}],
                concept_sample_id="unknown_id",
                user_id=None,
            )
            self.assertEqual(result.get("error"), "concept_sample_template_not_configured")
            mock_requests.post.assert_not_called()

    def test_configured_template_builds_n_audio_variables(self):
        """template_id 가 있다고 가정하면 audio1~audioN modifications 가 N개 생성된다."""
        from services import create_creatomate_video as ccv

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"id": "render-123"}

        with patch.object(ccv, "get_template_id", return_value="dummy-template-id"):
            with patch.object(ccv, "requests") as mock_requests:
                mock_requests.post.return_value = fake_response
                result = ccv.create_creatomate_video(
                    audio_paths=["a1.mp3", "a2.mp3", "a3.mp3"],
                    scripts=[{"script": "a"}, {"script": "b"}, {"script": "c"}],
                    concept_sample_id="sample_3",
                    user_id=None,
                )
        self.assertEqual(result, {"id": "render-123"})
        sent_payload = mock_requests.post.call_args.kwargs["data"]
        import json as _json
        payload = _json.loads(sent_payload)
        self.assertEqual(payload["template_id"], "dummy-template-id")
        for i in range(1, 4):
            self.assertIn(f"audio{i}.source", payload["modifications"])
        self.assertNotIn("audio4.source", payload["modifications"])


class TestGetCreatomateVarsGeneralized(unittest.TestCase):
    """data-model.md §4 — N-일반화된 시그니처(현재 라이브 경로 미사용, 대기 상태)."""

    def test_scene_count_four(self):
        from services.create_creatomate_video import get_creatomate_vars
        result = get_creatomate_vars([1.0, 2.0, 3.0, 4.0], 4)
        self.assertEqual(result["composition_4.time"], 6.0)  # 1+2+3
        self.assertEqual(result["composition_4.duration"], 4.0)
        self.assertEqual(result["duration"], 10.0)
        self.assertNotIn("composition_5.time", result)

    def test_scene_count_six(self):
        from services.create_creatomate_video import get_creatomate_vars
        durations = [1.0] * 6
        result = get_creatomate_vars(durations, 6)
        self.assertEqual(result["composition_6.time"], 5.0)
        self.assertEqual(result["duration"], 6.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
