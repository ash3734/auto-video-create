"""효과음 (2026-10-18, 백로그 3-5).

지키려는 것:
  · 안 고르면 그대로 (기존 결과물 유지)
  · 1번 장면에는 넣지 않는다 (첫마디가 묻힌다), 2번부터·끝 화면 시작에 넣는다
  · 공개 버킷이 아니다 (Pixabay 재배포 금지) — 만료되는 주소로만 넘긴다
  · 주소를 못 만들면 소리 없이 간다 (영상 생성을 막지 않는다)
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import bookends, layouts, sfx  # noqa: E402


def _with_sfx(src):
    return [c["name"] for c in src["elements"] if any(e.get("name") == "sfx" for e in c.get("elements") or [])]


class TestApply(unittest.TestCase):
    def setUp(self):
        self.src = layouts.get_source("letterbox", 5)
        p = mock.patch.object(sfx, "render_url", return_value="https://s3/sfx.mp3?sig")
        p.start(); self.addCleanup(p.stop)

    def test_default_changes_nothing(self):
        for raw in (None, "none", "모름"):
            self.assertEqual(json.dumps(sfx.apply(self.src, raw)), json.dumps(self.src))

    def test_from_second_scene(self):
        got = _with_sfx(sfx.apply(self.src, "whoosh"))
        self.assertEqual(got, ["composition_2", "composition_3", "composition_4", "composition_5"])

    def test_outro_start_too(self):
        v = {"image5.source": "x", "image5.visible": "true"}
        src = bookends.apply(self.src, "none", None, "comment", None, v)
        self.assertIn("composition_outro", _with_sfx(sfx.apply(src, "ding")))

    def test_volume_between_bgm_and_narration(self):
        out = sfx.apply(self.src, "pop")
        el = next(e for e in out["elements"][2]["elements"] if e.get("name") == "sfx")
        self.assertEqual(el["time"], 0)
        self.assertGreater(int(el["volume"].rstrip("%")), 15)     # 배경음악보다 크게
        self.assertLess(int(el["volume"].rstrip("%")), 100)       # 나레이션보다 작게

    def test_presign_failure_means_no_sound(self):
        with mock.patch.object(sfx, "render_url", return_value=None):
            self.assertEqual(json.dumps(sfx.apply(self.src, "whoosh")), json.dumps(self.src))


class TestStorage(unittest.TestCase):
    def test_private_bucket_and_expiry(self):
        self.assertNotEqual(sfx.BUCKET, "auto-video-tts-files")
        with mock.patch.object(sfx, "s3_client") as c:
            sfx.render_url("whoosh")
        self.assertLessEqual(c.return_value.generate_presigned_url.call_args.kwargs["ExpiresIn"], 3600)

    def test_missing_file_gives_no_url(self):
        """presigned 는 파일이 없어도 만들어진다 — 그 주소를 넘기면 렌더 전체가 실패한다."""
        with mock.patch.object(sfx, "s3_client") as c:
            c.return_value.head_object.side_effect = RuntimeError("404")
            self.assertIsNone(sfx.render_url("whoosh"))
        c.return_value.generate_presigned_url.assert_not_called()

    def test_license_recorded(self):
        for k, v in sfx.SOUNDS.items():
            if k == "none":
                continue
            self.assertTrue(v["source_page"].startswith("https://pixabay.com/"), k)
            self.assertEqual(v["license"], "Pixabay Content License")

    def test_listing_does_not_leak_cdn_or_bucket(self):
        with mock.patch.object(sfx, "s3_client") as c:
            c.return_value.generate_presigned_url.return_value = "https://signed"
            blob = json.dumps(sfx.available_sounds())
        self.assertNotIn("cdn.pixabay.com", blob)
        self.assertNotIn(sfx.BUCKET, blob)


class TestWiring(unittest.TestCase):
    def test_render_and_api(self):
        import services.create_creatomate_video as c
        import api.blog as blog
        with mock.patch.object(c, "get_template_id", return_value="tpl"), \
             mock.patch.object(sfx, "render_url", return_value="https://s3/sfx.mp3?sig"), \
             mock.patch.object(c, "requests") as rq:
            rq.post.return_value = mock.Mock(status_code=202, json=lambda: [{"id": "r1"}], text="")
            c.create_creatomate_video(["a.mp3"], ["대본"], title="t", user_id=None, scene_count=5, sound="whoosh")
        self.assertIn("https://s3/sfx.mp3?sig", rq.post.call_args.kwargs["data"])
        self.assertIsNone(blog.GenerateVideoRequest(title="t", scripts=["a"], sections=[]).sound)
        with mock.patch.object(sfx, "s3_client"):
            self.assertIn("none", [x["id"] for x in blog.get_effects()["sounds"]])


if __name__ == "__main__":
    unittest.main()
