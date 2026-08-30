"""배포용 문구(seo) — 단위 테스트 (2026-08-30).

유저 요청: "제목 설명 태그 등등도 생성" — 만든 영상을 유튜브/인스타/틱톡/페이스북에
올릴 때 쓸 문구다.

## 무엇을 지키려는가

**문구가 없다고 영상 제작이 막히면 안 된다.** 이건 부가 기능이고 영상이 본체다.
모델이 seo 를 빼먹든, 형태가 어긋나든, 파싱이 깨지든 빈 값으로 조용히 흐르고
스크립트 생성은 그대로 진행돼야 한다. 그래서 폴백 경로를 집중적으로 고정한다.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import summarize as sm  # noqa: E402


class TestNormalizeSeo(unittest.TestCase):
    def test_typical_response(self):
        got = sm.normalize_seo({
            "title": "일산 아파트 경매 분석",
            "description": "일산요진와이시티 84타입 경매 물건을 살펴봅니다.",
            "hashtags": ["부동산경매", "일산아파트", "법원경매"],
        })
        self.assertEqual(got["title"], "일산 아파트 경매 분석")
        self.assertEqual(got["hashtags"], ["부동산경매", "일산아파트", "법원경매"])

    def test_hash_prefix_stripped(self):
        """모델이 '#여행' 으로 주면 화면에서 다시 붙여 '##여행' 이 된다."""
        got = sm.normalize_seo({"title": "t", "description": "d",
                                "hashtags": ["#부동산", "##경매", " #일산 "]})
        self.assertEqual(got["hashtags"], ["부동산", "경매", "일산"])

    def test_spaces_removed_inside_tag(self):
        """해시태그에 공백이 있으면 거기서 끊긴다."""
        got = sm.normalize_seo({"title": "t", "description": "d",
                                "hashtags": ["법원 경매"]})
        self.assertEqual(got["hashtags"], ["법원경매"])

    def test_duplicates_removed_case_insensitively(self):
        got = sm.normalize_seo({"title": "t", "description": "d",
                                "hashtags": ["Seoul", "seoul", "서울", "서울"]})
        self.assertEqual(got["hashtags"], ["Seoul", "서울"])

    def test_capped_at_max(self):
        got = sm.normalize_seo({"title": "t", "description": "d",
                                "hashtags": [f"태그{i}" for i in range(50)]})
        self.assertEqual(len(got["hashtags"]), sm.MAX_HASHTAGS)

    def test_blank_and_nonstring_tags_dropped(self):
        got = sm.normalize_seo({"title": "t", "description": "d",
                                "hashtags": ["", "  ", "#", None, 3, [], "정상"]})
        self.assertEqual(got["hashtags"], ["정상"])

    def test_falls_back_to_video_title(self):
        """seo 제목이 없으면 영상 제목이라도 준다 — 빈 칸보다 낫다."""
        got = sm.normalize_seo(None, fallback_title="용인 아파트 경매")
        self.assertEqual(got["title"], "용인 아파트 경매")
        self.assertEqual(got["description"], "")
        self.assertEqual(got["hashtags"], [])

    def test_junk_shapes_never_raise(self):
        for bad in (None, "", [], 0, "문자열", {"hashtags": "태그"}, {"title": 3}):
            got = sm.normalize_seo(bad)
            self.assertEqual(set(got), {"title", "description", "hashtags"}, repr(bad))
            self.assertIsInstance(got["hashtags"], list)

    def test_returned_shape_is_always_complete(self):
        """FE 가 세 키의 존재를 전제로 그린다."""
        got = sm.normalize_seo({"title": "t"})
        self.assertEqual(set(got), {"title", "description", "hashtags"})


class TestSchema(unittest.TestCase):
    def test_seo_required_in_both_schemas(self):
        for with_images in (False, True):
            schema = sm.build_shorts_output_schema(5, with_images=with_images)
            self.assertIn("seo", schema["properties"], with_images)
            self.assertIn("seo", schema["required"], with_images)

    def test_scene_count_still_enforced(self):
        """seo 를 얹다가 기존 장면 수 강제가 깨지면 안 된다."""
        schema = sm.build_shorts_output_schema(7, with_images=True)
        self.assertEqual(schema["properties"]["scripts"]["minItems"], 7)
        self.assertEqual(schema["properties"]["scripts"]["maxItems"], 7)


class TestPipelineFallbacks(unittest.TestCase):
    """어떤 실패든 (title, scripts, seo) 3개를 돌려줘야 호출부가 안 터진다."""

    def _run(self, content):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False), \
             mock.patch.object(sm, "_generate_with_openai", return_value=content):
            return sm.summarize_for_shorts_sets("본문", category="general", scene_count=2)

    def test_model_omits_seo(self):
        title, scripts, seo = self._run(
            '{"title":"제목","scripts":[{"script":"가"},{"script":"나"}]}')
        self.assertEqual(title, "제목")
        self.assertEqual(len(scripts), 2)
        self.assertEqual(seo["hashtags"], [])
        self.assertEqual(seo["title"], "제목")   # 영상 제목으로 폴백

    def test_model_returns_seo(self):
        _, _, seo = self._run(
            '{"title":"제목","scripts":[{"script":"가"},{"script":"나"}],'
            '"seo":{"title":"배포제목","description":"설명","hashtags":["#경매"]}}')
        self.assertEqual(seo["title"], "배포제목")
        self.assertEqual(seo["hashtags"], ["경매"])

    def test_unparseable_response_still_returns_three(self):
        title, scripts, seo = self._run("이건 JSON 이 아니다")
        self.assertEqual((title, scripts), ("", []))
        self.assertEqual(seo, sm.EMPTY_SEO)

    def test_none_content_still_returns_three(self):
        self.assertEqual(len(self._run(None)), 3)

    def test_api_failure_still_returns_three(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False), \
             mock.patch.object(sm, "_generate_with_openai", side_effect=RuntimeError("boom")):
            got = sm.summarize_for_shorts_sets("본문", scene_count=2)
        self.assertEqual(len(got), 3)
        self.assertEqual(got[2], sm.EMPTY_SEO)


class TestTokenBudget(unittest.TestCase):
    def test_fallback_ceiling_raised(self):
        """실측: 장면 10개 응답이 이미 약 570 토큰. 700 이면 seo 를 얹을 때 잘린다."""
        import inspect

        src = inspect.getsource(sm._generate_with_openai)
        self.assertIn("max_tokens=1500", src)


if __name__ == "__main__":
    unittest.main()
