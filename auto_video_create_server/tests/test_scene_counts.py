"""장면 수(scene_count) 선택 기능 — 단위 테스트.

대상 (외부 API 없음):
- services.scene_counts : 정규화 / 템플릿 룩업(ENV 분기) / suffix / 가용 목록
- services.summarize    : build_shorts_output_schema / _normalize_scripts
"""
import importlib
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import scene_counts as sc  # noqa: E402
from services.summarize import build_shorts_output_schema, _normalize_scripts  # noqa: E402


class TestNormalizeSceneCount(unittest.TestCase):
    def test_allowed_values_pass_through(self):
        for n in [4, 5, 6, 7, 8]:
            self.assertEqual(sc.normalize_scene_count(n), n)

    def test_out_of_range_falls_back_to_default(self):
        for bad in [0, 3, 9, 100, -5]:
            self.assertEqual(sc.normalize_scene_count(bad), sc.DEFAULT_SCENE_COUNT)

    def test_none_and_garbage_fall_back(self):
        for bad in [None, "", "abc", [], {}, 4.7]:
            self.assertEqual(sc.normalize_scene_count(bad), sc.DEFAULT_SCENE_COUNT)

    def test_numeric_string_accepted(self):
        self.assertEqual(sc.normalize_scene_count("6"), 6)

    def test_bool_rejected(self):
        # True 는 int 서브클래스라 1 로 해석될 수 있음 — 명시적으로 거부
        self.assertEqual(sc.normalize_scene_count(True), sc.DEFAULT_SCENE_COUNT)


class TestTemplateLookup(unittest.TestCase):
    def test_default_5_is_configured(self):
        """5장면은 기존 운영 템플릿이 있으므로 항상 사용 가능해야 한다."""
        self.assertTrue(sc.is_configured(5))
        self.assertIsNotNone(sc.get_template_id(5))

    def test_unconfigured_counts_return_none(self):
        for n in [4, 6, 7, 8]:
            self.assertIsNone(sc.get_template_id(n), f"{n}장면은 아직 placeholder여야 함")
            self.assertFalse(sc.is_configured(n))

    def test_env_switches_template_id(self):
        with mock.patch.dict(os.environ, {"ENV": "production"}):
            prod_id = sc.get_template_id(5)
        with mock.patch.dict(os.environ, {"ENV": "test"}):
            test_id = sc.get_template_id(5)
        self.assertNotEqual(prod_id, test_id)
        self.assertEqual(prod_id, sc.SCENE_COUNT_CONFIG[5]["template_id_prod"])
        self.assertEqual(test_id, sc.SCENE_COUNT_CONFIG[5]["template_id_test"])

    def test_invalid_scene_count_uses_default_config(self):
        self.assertEqual(sc.get_template_id(99), sc.get_template_id(5))


class TestSubtitleSuffixes(unittest.TestCase):
    def test_5_has_suffixes_matching_count(self):
        suffixes = sc.get_subtitle_suffixes(5)
        self.assertIsNotNone(suffixes)
        self.assertEqual(len(suffixes), 5, "자막 suffix 개수는 장면 수와 같아야 함")

    def test_unconfigured_returns_none(self):
        for n in [4, 6, 7, 8]:
            self.assertIsNone(sc.get_subtitle_suffixes(n))

    def test_configured_counts_have_matching_suffix_length(self):
        """템플릿을 채울 때 suffix 개수를 장면 수와 맞추라는 계약을 강제."""
        for n, config in sc.SCENE_COUNT_CONFIG.items():
            suffixes = config.get("subtitle_suffixes")
            if suffixes is not None:
                self.assertEqual(len(suffixes), n, f"{n}장면 suffix 개수 불일치")


class TestAvailableSceneCounts(unittest.TestCase):
    def test_lists_all_five_options(self):
        options = sc.available_scene_counts()
        self.assertEqual([o["scene_count"] for o in options], [4, 5, 6, 7, 8])

    def test_exactly_one_default(self):
        options = sc.available_scene_counts()
        defaults = [o for o in options if o["is_default"]]
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0]["scene_count"], 5)

    def test_availability_reflects_config(self):
        options = {o["scene_count"]: o["available"] for o in sc.available_scene_counts()}
        self.assertTrue(options[5])
        self.assertFalse(options[4])


class TestBuildSchema(unittest.TestCase):
    def test_min_max_items_match_scene_count(self):
        for n in [4, 5, 6, 7, 8]:
            schema = build_shorts_output_schema(n)
            self.assertEqual(schema["properties"]["scripts"]["minItems"], n)
            self.assertEqual(schema["properties"]["scripts"]["maxItems"], n)

    def test_with_images_includes_image_index(self):
        schema = build_shorts_output_schema(6, with_images=True)
        props = schema["properties"]["scripts"]["items"]["properties"]
        self.assertIn("image_index", props)

    def test_without_images_has_no_image_index(self):
        schema = build_shorts_output_schema(6, with_images=False)
        props = schema["properties"]["scripts"]["items"]["properties"]
        self.assertNotIn("image_index", props)

    def test_does_not_mutate_base_schema(self):
        from services.summarize import SHORTS_OUTPUT_SCHEMA
        build_shorts_output_schema(8)
        self.assertNotIn("minItems", SHORTS_OUTPUT_SCHEMA["properties"]["scripts"])


class TestNormalizeScripts(unittest.TestCase):
    def _scripts(self, n):
        return [{"script": f"s{i}"} for i in range(n)]

    def test_exact_count_unchanged(self):
        out = _normalize_scripts(self._scripts(6), 6)
        self.assertEqual(len(out), 6)

    def test_too_few_padded(self):
        out = _normalize_scripts(self._scripts(3), 7)
        self.assertEqual(len(out), 7)
        self.assertEqual(out[-1], {"script": ""})

    def test_one_extra_keeps_last(self):
        """N+1 개일 때 마무리 멘트(마지막)를 살리는 기존 동작 계승."""
        out = _normalize_scripts(self._scripts(6), 5)
        self.assertEqual(len(out), 5)
        self.assertEqual(out[-1]["script"], "s5")

    def test_many_extra_truncated(self):
        out = _normalize_scripts(self._scripts(10), 4)
        self.assertEqual(len(out), 4)
        self.assertEqual([s["script"] for s in out], ["s0", "s1", "s2", "s3"])

    def test_non_list_returns_empty_scripts(self):
        out = _normalize_scripts(None, 4)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(s == {"script": ""} for s in out))


if __name__ == "__main__":
    unittest.main()
