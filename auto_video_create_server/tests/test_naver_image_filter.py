"""네이버 크롤러 이미지 URL 필터 — 단위 테스트.

스티커/이모티콘 CDN 이 본문 사진으로 섞이면 갤러리 엑박 + Creatomate 렌더 실패로
이어지므로(BUG-008 및 2026-08-04 cafe_001 사례) 필터를 회귀 테스트로 고정한다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.naver import _is_valid_naver_image_url as is_valid  # noqa: E402


class TestNaverImageFilter(unittest.TestCase):

    def test_normal_blog_photo_allowed(self):
        self.assertTrue(is_valid(
            "https://postfiles.pstatic.net/MjAyNTA1MDlfMTYg/MDAx.JPEG/IMG_2224.JPG?type=w966"
        ))

    def test_blogfiles_allowed(self):
        self.assertTrue(is_valid("https://blogfiles.pstatic.net/some/photo.png"))

    def test_ogq_sticker_blocked(self):
        """BUG-008 회귀 방지."""
        self.assertFalse(is_valid(
            "https://storep-phinf.pstatic.net/ogq_5d0a/original_3.png?type=w966"
        ))

    def test_cafe_sticker_blocked(self):
        """2026-08-04: Creatomate 다운로드 실패(404)를 유발한 실제 URL.

        BUG-008 이 `/ogq_` 경로만 막아 이 URL 이 통과했었다.
        """
        self.assertFalse(is_valid(
            "https://storep-phinf.pstatic.net/cafe_001/original_9.gif?type=w966"
        ))

    def test_any_storep_path_blocked(self):
        """경로가 아니라 도메인 단위로 막혀야 한다 (새 스티커 경로 대비)."""
        for path in ["ogq_x/a.png", "cafe_001/b.gif", "line_002/c.png", "unknown_new/d.jpg"]:
            self.assertFalse(
                is_valid(f"https://storep-phinf.pstatic.net/{path}"),
                f"{path} 가 통과했습니다",
            )

    def test_non_pstatic_host_blocked(self):
        self.assertFalse(is_valid("https://example.com/photo.jpg"))

    def test_non_http_scheme_blocked(self):
        self.assertFalse(is_valid("data:image/png;base64,iVBOR"))
        self.assertFalse(is_valid("//postfiles.pstatic.net/a.jpg"))


if __name__ == "__main__":
    unittest.main()
