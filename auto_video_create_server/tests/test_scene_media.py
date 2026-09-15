"""사진 장면 변수 — 단위 테스트 (2026-09-15).

사진 틀(720×640)과 비율이 다른 사진이 잘리던 문제. fit 이 빠지면 Creatomate 기본값
cover 로 돌아가 휴대폰 세로 사진의 위아래 3분의 1이 다시 잘린다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.scene_media import IMAGE_FIT, image_slot_variables  # noqa: E402


class TestImageSlotVariables(unittest.TestCase):
    def test_photo_is_not_cropped(self):
        v = image_slot_variables(3, "https://example.com/a.jpg")
        self.assertEqual(v["image3.fit"], "contain")

    def test_fit_is_contain_not_cover(self):
        """cover 는 템플릿 기본값과 같아서 넣으나 마나다."""
        self.assertEqual(IMAGE_FIT, "contain")

    def test_keeps_existing_visibility_contract(self):
        """영상 요소를 끄고 사진 요소를 켜는 기존 동작은 그대로여야 한다."""
        v = image_slot_variables(1, "https://example.com/a.jpg")
        self.assertEqual(v["image1.source"], "https://example.com/a.jpg")
        self.assertEqual(v["image1.visible"], "true")
        self.assertEqual(v["video1.visible"], "false")

    def test_slot_number_used_for_every_key(self):
        """다른 장면 번호의 요소를 건드리면 엉뚱한 장면의 사진이 바뀐다."""
        v = image_slot_variables(8, "x")
        self.assertTrue(all(k.startswith(("image8.", "video8.")) for k in v), v)


if __name__ == "__main__":
    unittest.main()
