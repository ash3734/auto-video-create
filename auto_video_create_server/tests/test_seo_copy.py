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
            self.assertEqual(set(got), {"title", "description", "description_long", "hashtags"}, repr(bad))
            self.assertIsInstance(got["hashtags"], list)

    def test_returned_shape_is_always_complete(self):
        """FE 가 세 키의 존재를 전제로 그린다."""
        got = sm.normalize_seo({"title": "t"})
        self.assertEqual(set(got), {"title", "description", "description_long", "hashtags"})


class TestLongDescription(unittest.TestCase):
    """유튜브 설명란은 검색 재료라 짧으면 손해다 (PO 지적, 2026-08-30)."""

    def test_long_description_kept(self):
        got = sm.normalize_seo({
            "title": "t", "description": "짧은 것",
            "description_long": "유튜브용 긴 설명입니다. " * 5, "hashtags": [],
        })
        self.assertIn("유튜브용 긴 설명", got["description_long"])
        self.assertEqual(got["description"], "짧은 것")

    def test_falls_back_to_short_when_missing(self):
        """유튜브 탭이 빈 칸이 되는 것보다 짧게라도 채우는 편이 낫다."""
        got = sm.normalize_seo({"title": "t", "description": "짧은 것", "hashtags": []})
        self.assertEqual(got["description_long"], "짧은 것")

    def test_both_empty_stays_empty(self):
        got = sm.normalize_seo({"title": "t", "hashtags": []})
        self.assertEqual(got["description_long"], "")

    def test_prompt_no_longer_caps_at_three_sentences(self):
        """'2~3문장' 이라고 못 박아 둔 게 설명이 짧았던 직접 원인이었다."""
        self.assertNotIn("description: 2~3문장", sm.SEO_ADDENDUM)
        self.assertIn("description_long", sm.SEO_ADDENDUM)

    def test_prompt_asks_for_exact_hashtag_count(self):
        """15개를 요청했는데 5개가 왔다 — 개수를 강하게 요구한다."""
        self.assertIn("정확히 15개", sm.SEO_ADDENDUM)


class TestSchema(unittest.TestCase):
    def test_seo_required_in_both_schemas(self):
        for with_images in (False, True):
            schema = sm.build_shorts_output_schema(5, with_images=with_images)
            self.assertIn("seo", schema["properties"], with_images)
            self.assertIn("seo", schema["required"], with_images)
            seo = schema["properties"]["seo"]
            self.assertIn("description_long", seo["properties"], with_images)
            self.assertIn("description_long", seo["required"], with_images)

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


class TestModelChoice(unittest.TestCase):
    """모델을 되돌리면 문구 품질과 JSON 안정성이 같이 내려간다 (2026-08-30 비교)."""

    def test_not_on_gpt_3_5(self):
        self.assertNotIn("3.5", sm.OPENAI_MODEL)

    def test_model_is_used_by_the_fallback(self):
        """상수만 바꾸고 호출부가 옛 모델을 쓰면 아무 의미가 없다."""
        import inspect

        src = inspect.getsource(sm._generate_with_openai)
        self.assertIn("model=OPENAI_MODEL", src)


class TestTokenBudget(unittest.TestCase):
    def test_fallback_ceiling_raised(self):
        """실측: 장면 10개 응답이 약 570 토큰. 유튜브용 긴 설명(200~400자)까지
        더하면 1,500 도 빠듯해 2,500 으로 올렸다. 잘리면 스크립트까지 깨진다."""
        import inspect

        src = inspect.getsource(sm._generate_with_openai)
        self.assertIn("max_tokens=2500", src)


if __name__ == "__main__":
    unittest.main()
