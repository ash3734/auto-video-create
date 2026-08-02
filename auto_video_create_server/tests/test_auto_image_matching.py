"""VOC-2 이미지 자동 매칭 — 후처리 로직 단위 테스트.

대상 (순수 함수만 — 외부 API/크롤링 없음):
- services.blog_shorts._normalize_image_indices : 1-based → 0-based, 무효/중복 제거, dict 에서 키 제거
- services.blog_shorts._build_suggested_sections : LLM 매칭 + 위치 폴백 + default 채움
- services.summarize._format_image_list_for_prompt : 프롬프트 목록 포맷
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.blog_shorts import (  # noqa: E402
    _normalize_image_indices,
    _build_suggested_sections,
)
from services.summarize import _format_image_list_for_prompt  # noqa: E402

IMAGES = ["u0", "u1", "u2", "u3", "u4"]


class TestNormalizeImageIndices(unittest.TestCase):
    def test_valid_one_based_converted(self):
        scripts = [{"script": "a", "image_index": 1}, {"script": "b", "image_index": 3}]
        self.assertEqual(_normalize_image_indices(scripts, 5), [0, 2])

    def test_image_index_removed_from_scripts(self):
        scripts = [{"script": "a", "image_index": 1}]
        _normalize_image_indices(scripts, 5)
        self.assertNotIn("image_index", scripts[0])

    def test_null_and_missing_become_none(self):
        scripts = [{"script": "a", "image_index": None}, {"script": "b"}]
        self.assertEqual(_normalize_image_indices(scripts, 5), [None, None])

    def test_out_of_range_invalid(self):
        scripts = [
            {"script": "a", "image_index": 0},   # 1-based 이므로 0 은 무효
            {"script": "b", "image_index": 6},   # 범위 밖
            {"script": "c", "image_index": -1},
        ]
        self.assertEqual(_normalize_image_indices(scripts, 5), [None, None, None])

    def test_duplicate_first_wins(self):
        scripts = [
            {"script": "a", "image_index": 2},
            {"script": "b", "image_index": 2},  # 중복 → None
        ]
        self.assertEqual(_normalize_image_indices(scripts, 5), [1, None])

    def test_bool_and_str_invalid(self):
        scripts = [
            {"script": "a", "image_index": True},   # bool 은 int 서브클래스지만 거부
            {"script": "b", "image_index": "2"},
        ]
        self.assertEqual(_normalize_image_indices(scripts, 5), [None, None])


class TestBuildSuggestedSections(unittest.TestCase):
    def test_all_matched(self):
        sections = _build_suggested_sections([0, 2], IMAGES)
        self.assertEqual(sections, [
            {"type": "image", "url": "u0"},
            {"type": "image", "url": "u2"},
        ])

    def test_position_fallback_skips_used(self):
        # 두 번째 슬롯 None → 아직 안 쓰인 이미지 중 가장 앞(u1)
        sections = _build_suggested_sections([0, None, 2], IMAGES)
        self.assertEqual(sections[1], {"type": "image", "url": "u1"})

    def test_all_none_falls_back_in_order(self):
        # LLM 이 전부 null 이어도 (OpenAI 폴백 미지원 응답 등) 순서대로 자동 채움
        sections = _build_suggested_sections([None, None, None], IMAGES)
        self.assertEqual([s["url"] for s in sections], ["u0", "u1", "u2"])

    def test_default_when_images_exhausted(self):
        sections = _build_suggested_sections([None, None, None], ["u0"])
        self.assertEqual(sections[0], {"type": "image", "url": "u0"})
        self.assertEqual(sections[1], {"type": "default", "url": None})
        self.assertEqual(sections[2], {"type": "default", "url": None})

    def test_no_images_all_default(self):
        sections = _build_suggested_sections([None, None], [])
        self.assertEqual(sections, [
            {"type": "default", "url": None},
            {"type": "default", "url": None},
        ])

    def test_length_matches_scripts(self):
        self.assertEqual(len(_build_suggested_sections([None] * 5, IMAGES)), 5)


class TestFormatImageList(unittest.TestCase):
    def test_caption_preferred_over_context(self):
        infos = [{"url": "u", "caption": "본죽 사진", "context": "주변텍스트"}]
        self.assertIn("[1] 본죽 사진", _format_image_list_for_prompt(infos))

    def test_context_fallback_and_empty(self):
        infos = [
            {"url": "u", "caption": "", "context": "주변 텍스트"},
            {"url": "u2", "caption": "", "context": ""},
        ]
        out = _format_image_list_for_prompt(infos)
        self.assertIn("[1] 주변 텍스트", out)
        self.assertIn("[2] (설명 없음)", out)

    def test_limit_20(self):
        infos = [{"url": f"u{i}", "caption": f"c{i}", "context": ""} for i in range(30)]
        out = _format_image_list_for_prompt(infos)
        self.assertIn("[20]", out)
        self.assertNotIn("[21]", out)


if __name__ == "__main__":
    unittest.main()
