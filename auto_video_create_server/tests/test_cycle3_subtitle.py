"""
test_cycle3_subtitle.py — cycle-3 자막 스타일 단위 테스트

외부 의존성(S3, Google Fonts API, Creatomate) 없이 순수 로직만 검증.
pytest 없이 stdlib unittest 사용 (서버 환경 최소 의존).
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 서버 루트를 sys.path 에 추가
_SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SERVER_ROOT not in sys.path:
    sys.path.insert(0, _SERVER_ROOT)


# ─────────────────────────────────────────────
# font_service 테스트
# ─────────────────────────────────────────────

class TestFontService(unittest.TestCase):

    def test_build_slug_basic(self):
        """폰트 이름 → slug 변환 규칙 검증."""
        from services.font_service import _build_slug
        self.assertEqual(_build_slug("Noto Sans KR"), "noto-sans-kr")
        self.assertEqual(_build_slug("Black Han Sans"), "black-han-sans")
        self.assertEqual(_build_slug("Do Hyeon"), "do-hyeon")
        self.assertEqual(_build_slug("Nanum Gothic"), "nanum-gothic")

    def test_fallback_fonts_structure(self):
        """fallback 목록 구조 검증 — family/category/slug 모두 있어야 함."""
        from services.font_service import FALLBACK_FONTS
        self.assertGreater(len(FALLBACK_FONTS), 0)
        for font in FALLBACK_FONTS:
            self.assertIn("family", font, f"family 없음: {font}")
            self.assertIn("category", font, f"category 없음: {font}")
            self.assertIn("slug", font, f"slug 없음: {font}")
            self.assertIsInstance(font["family"], str)
            self.assertIsInstance(font["category"], str)
            self.assertIsInstance(font["slug"], str)

    def test_get_korean_fonts_fallback_on_missing_key(self):
        """GOOGLE_FONTS_API_KEY 없을 때 fallback 반환."""
        # lru_cache 초기화 필요
        from services import font_service
        font_service._fetch_korean_fonts_cached.cache_clear()

        with patch.dict(os.environ, {}, clear=True):
            # GOOGLE_FONTS_API_KEY 제거
            os.environ.pop("GOOGLE_FONTS_API_KEY", None)
            fonts = font_service.get_korean_fonts()
            self.assertIsInstance(fonts, list)
            self.assertGreater(len(fonts), 0)
            # fallback 의 첫 번째 항목 확인 (알파벳순: Black Han Sans)
            families = [f["family"] for f in fonts]
            self.assertIn("Black Han Sans", families)

        # 캐시 다시 초기화 (다른 테스트에 영향 없도록)
        font_service._fetch_korean_fonts_cached.cache_clear()

    def test_get_allowed_font_families_returns_set(self):
        """get_allowed_font_families 가 set 을 반환하는지 확인."""
        from services import font_service
        font_service._fetch_korean_fonts_cached.cache_clear()
        os.environ.pop("GOOGLE_FONTS_API_KEY", None)
        families = font_service.get_allowed_font_families()
        self.assertIsInstance(families, set)
        self.assertIn("Noto Sans KR", families)
        font_service._fetch_korean_fonts_cached.cache_clear()


# ─────────────────────────────────────────────
# subtitle_settings_service 테스트
# ─────────────────────────────────────────────

class TestValidateSubtitleSettings(unittest.TestCase):

    def _make_valid_settings(self):
        return {
            "title": {
                "font_family": "Black Han Sans",
                "font_size": "M",
                "fill_color": "#fff100",
            },
            "subtitle": {
                "font_family": "Noto Sans KR",
                "font_size": "M",
                "fill_color": "#ffffff",
            },
        }

    def test_valid_settings_no_errors(self):
        from services.subtitle_settings_service import validate_subtitle_settings
        settings = self._make_valid_settings()
        allowed = {"Black Han Sans", "Noto Sans KR"}
        errors = validate_subtitle_settings(settings, allowed)
        self.assertEqual(errors, [])

    def test_invalid_font_size(self):
        from services.subtitle_settings_service import validate_subtitle_settings
        settings = self._make_valid_settings()
        settings["title"]["font_size"] = "XL"
        errors = validate_subtitle_settings(settings, {"Black Han Sans", "Noto Sans KR"})
        self.assertTrue(any("font_size" in e for e in errors))

    def test_invalid_hex_color(self):
        from services.subtitle_settings_service import validate_subtitle_settings
        settings = self._make_valid_settings()
        settings["subtitle"]["fill_color"] = "red"  # 유효하지 않은 hex
        errors = validate_subtitle_settings(settings, {"Black Han Sans", "Noto Sans KR"})
        self.assertTrue(any("fill_color" in e for e in errors))

    def test_invalid_font_family_not_in_allowed(self):
        from services.subtitle_settings_service import validate_subtitle_settings
        settings = self._make_valid_settings()
        settings["title"]["font_family"] = "Comic Sans"  # 한글 지원 아님
        allowed = {"Black Han Sans", "Noto Sans KR"}
        errors = validate_subtitle_settings(settings, allowed)
        self.assertTrue(any("font_family" in e for e in errors))

    def test_empty_allowed_families_skips_font_check(self):
        """Google Fonts API 장애 시 허용 목록 비어있으면 font_family 검증 완화."""
        from services.subtitle_settings_service import validate_subtitle_settings
        settings = self._make_valid_settings()
        settings["title"]["font_family"] = "AnyFont"
        errors = validate_subtitle_settings(settings, set())  # 빈 set
        self.assertEqual(errors, [])

    def test_missing_subtitle_section(self):
        from services.subtitle_settings_service import validate_subtitle_settings
        settings = {"title": self._make_valid_settings()["title"]}  # subtitle 누락
        errors = validate_subtitle_settings(settings, {"Black Han Sans"})
        self.assertTrue(any("subtitle" in e for e in errors))

    def test_hex_color_lowercase_valid(self):
        from services.subtitle_settings_service import validate_subtitle_settings
        settings = self._make_valid_settings()
        settings["subtitle"]["fill_color"] = "#ff0000"
        errors = validate_subtitle_settings(settings, {"Black Han Sans", "Noto Sans KR"})
        self.assertEqual(errors, [])

    def test_hex_color_uppercase_valid(self):
        from services.subtitle_settings_service import validate_subtitle_settings
        settings = self._make_valid_settings()
        settings["subtitle"]["fill_color"] = "#FF0000"
        errors = validate_subtitle_settings(settings, {"Black Han Sans", "Noto Sans KR"})
        self.assertEqual(errors, [])


class TestApplySubtitleSettingsToVariables(unittest.TestCase):

    def test_none_settings_does_nothing(self):
        """subtitle_settings=None 이면 variables 변경 없음."""
        from services.subtitle_settings_service import apply_subtitle_settings_to_variables
        variables = {}
        apply_subtitle_settings_to_variables(variables, None)
        self.assertEqual(variables, {})

    def test_empty_settings_does_nothing(self):
        from services.subtitle_settings_service import apply_subtitle_settings_to_variables
        variables = {}
        apply_subtitle_settings_to_variables(variables, {})
        self.assertEqual(variables, {})

    def test_full_settings_injects_all(self):
        """완전한 설정값 → title + 5개 subtitle 모두 주입."""
        from services.subtitle_settings_service import apply_subtitle_settings_to_variables, SUBTITLE_SUFFIXES
        settings = {
            "title": {
                "font_family": "Black Han Sans",
                "font_size": "L",
                "fill_color": "#fff100",
            },
            "subtitle": {
                "font_family": "Noto Sans KR",
                "font_size": "S",
                "fill_color": "#ffffff",
            },
        }
        variables = {}
        apply_subtitle_settings_to_variables(variables, settings)

        # 제목 검증
        self.assertEqual(variables["title.font_family"], "Black Han Sans")
        self.assertEqual(variables["title.fill_color"], "#fff100")
        self.assertEqual(variables["title.font_size"], "12 vmin")  # L

        # 자막 5개 검증
        for suffix in SUBTITLE_SUFFIXES:
            self.assertEqual(variables[f"Subtitles-{suffix}.font_family"], "Noto Sans KR")
            self.assertEqual(variables[f"Subtitles-{suffix}.font_size"], "4 vmin")   # S
            self.assertEqual(variables[f"Subtitles-{suffix}.fill_color"], "#ffffff")

    def test_title_size_M_not_injected(self):
        """제목 font_size=M 이면 title.font_size 미주입 (auto-fit 유지)."""
        from services.subtitle_settings_service import apply_subtitle_settings_to_variables
        settings = {
            "title": {
                "font_family": "Black Han Sans",
                "font_size": "M",
                "fill_color": "#fff100",
            },
            "subtitle": {
                "font_family": "Noto Sans KR",
                "font_size": "M",
                "fill_color": "#ffffff",
            },
        }
        variables = {}
        apply_subtitle_settings_to_variables(variables, settings)
        self.assertNotIn("title.font_size", variables)

    def test_subtitle_size_M_is_6vmin(self):
        """자막 font_size=M → 6 vmin (기존 템플릿 기본값과 동일)."""
        from services.subtitle_settings_service import apply_subtitle_settings_to_variables, SUBTITLE_SUFFIXES
        settings = {
            "title": {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
            "subtitle": {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
        }
        variables = {}
        apply_subtitle_settings_to_variables(variables, settings)
        for suffix in SUBTITLE_SUFFIXES:
            self.assertEqual(variables[f"Subtitles-{suffix}.font_size"], "6 vmin")

    def test_subtitle_size_L_is_8vmin(self):
        from services.subtitle_settings_service import apply_subtitle_settings_to_variables, SUBTITLE_SUFFIXES
        settings = {
            "title": {"font_family": "Black Han Sans", "font_size": "M", "fill_color": "#fff100"},
            "subtitle": {"font_family": "Noto Sans KR", "font_size": "L", "fill_color": "#ffffff"},
        }
        variables = {}
        apply_subtitle_settings_to_variables(variables, settings)
        for suffix in SUBTITLE_SUFFIXES:
            self.assertEqual(variables[f"Subtitles-{suffix}.font_size"], "8 vmin")

    def test_5_subtitle_elements_all_set(self):
        """자막 element 정확히 5개(6K5/JTM/MDV/5Z2/D6M) 모두 키 생성."""
        from services.subtitle_settings_service import apply_subtitle_settings_to_variables, SUBTITLE_SUFFIXES
        settings = {
            "title": {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#fff100"},
            "subtitle": {"font_family": "Noto Sans KR", "font_size": "M", "fill_color": "#ffffff"},
        }
        variables = {}
        apply_subtitle_settings_to_variables(variables, settings)
        self.assertEqual(len(SUBTITLE_SUFFIXES), 5)
        for suffix in SUBTITLE_SUFFIXES:
            self.assertIn(f"Subtitles-{suffix}.font_family", variables)
            self.assertIn(f"Subtitles-{suffix}.font_size", variables)
            self.assertIn(f"Subtitles-{suffix}.fill_color", variables)

    def test_existing_variables_not_overwritten_by_none_settings(self):
        """settings=None 이면 기존 variables 그대로 유지."""
        from services.subtitle_settings_service import apply_subtitle_settings_to_variables
        variables = {"image1.source": "https://example.com/img.jpg"}
        apply_subtitle_settings_to_variables(variables, None)
        self.assertIn("image1.source", variables)


class TestSubtitleSuffixes(unittest.TestCase):
    def test_suffix_list_exact(self):
        """SUBTITLE_SUFFIXES 가 정확히 architecture.md DEP-01 확인값과 일치."""
        from services.subtitle_settings_service import SUBTITLE_SUFFIXES
        self.assertEqual(SUBTITLE_SUFFIXES, ["6K5", "JTM", "MDV", "5Z2", "D6M"])


class TestSizeMapConstants(unittest.TestCase):
    def test_size_map_subtitle_vmin(self):
        from services.subtitle_settings_service import SIZE_MAP_SUBTITLE_VMIN
        self.assertEqual(SIZE_MAP_SUBTITLE_VMIN["S"], "4 vmin")
        self.assertEqual(SIZE_MAP_SUBTITLE_VMIN["M"], "6 vmin")
        self.assertEqual(SIZE_MAP_SUBTITLE_VMIN["L"], "8 vmin")

    def test_size_map_title_vmin(self):
        from services.subtitle_settings_service import SIZE_MAP_TITLE_VMIN
        self.assertEqual(SIZE_MAP_TITLE_VMIN["S"], "6 vmin")
        self.assertIsNone(SIZE_MAP_TITLE_VMIN["M"])   # auto-fit → None
        self.assertEqual(SIZE_MAP_TITLE_VMIN["L"], "12 vmin")


if __name__ == "__main__":
    unittest.main(verbosity=2)
