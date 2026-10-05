"""내가 만든 영상 — 단위 테스트 (2026-10-05, 백로그 4-1).

지키려는 것:
  · Creatomate 는 30일 뒤 영상을 지운다 → 완성되면 우리 S3 로 옮기고, 그 주소로 보여준다
  · 옮기기가 실패해도 웹훅·목록이 깨지지 않는다
  · 오래 "만드는 중"인 기록은 직접 물어 고친다 (웹훅이 안 온 건)
  · 한 번 조회에서 고치는 수에 상한이 있다 (API Gateway 29초)
  · 화면에 내부 키(S3 경로, user_id)를 내보내지 않는다
"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import render_files, render_store  # noqa: E402

DAY = 86400


def _rec(rid, status="succeeded", age=60, **kw):
    """age 초 전에 접수된 기록."""
    submitted = (datetime.now(render_store.KST) - timedelta(seconds=age)).isoformat(timespec="seconds")
    r = {"render_id": rid, "user_id": "u1", "status": status, "title": "제목",
         "submitted_at": submitted, "url": f"https://creatomate/{rid}.mp4"}
    r.update(kw)
    return r


class TestMirror(unittest.TestCase):
    def test_copies_to_private_bucket(self):
        with mock.patch.object(render_files.requests, "get",
                               return_value=mock.Mock(status_code=200, content=b"MP4")), \
             mock.patch.object(render_files, "s3_client") as s3:
            got = render_files.mirror("r1", "https://creatomate/r1.mp4")
        kw = s3.return_value.put_object.call_args.kwargs
        self.assertEqual(kw["Bucket"], "blog-to-short-form-credits")
        self.assertEqual(kw["Key"], "renders/files/r1.mp4")
        self.assertEqual(kw["ContentType"], "video/mp4")
        self.assertEqual(got["video_key"], "renders/files/r1.mp4")

    def test_never_public_bucket(self):
        """auto-video-tts-files 는 정책상 공개 버킷이다 — 유저 영상이 주소만으로 열린다."""
        self.assertNotEqual(render_files.BUCKET, "auto-video-tts-files")

    def test_no_url_means_no_network(self):
        with mock.patch.object(render_files.requests, "get") as g:
            self.assertIsNone(render_files.mirror("r1", None))
        g.assert_not_called()

    def test_failure_returns_none(self):
        for side in (RuntimeError("timeout"), None):
            resp = mock.Mock(status_code=404, content=b"") if side is None else None
            with mock.patch.object(render_files.requests, "get",
                                   side_effect=side, return_value=resp), \
                 mock.patch.object(render_files, "s3_client") as s3:
                self.assertIsNone(render_files.mirror("r1", "https://x"))
            s3.return_value.put_object.assert_not_called()


class TestDownloadName(unittest.TestCase):
    def test_strips_unsafe_chars(self):
        self.assertEqual(render_files.download_name('a/b:c*?"d', None), "a b c d.mp4")

    def test_falls_back_to_date(self):
        self.assertEqual(render_files.download_name("  ", "2026-10-05T10:00:00+09:00"),
                         "shorts_20261005.mp4")

    def test_korean_title_kept(self):
        self.assertEqual(render_files.download_name("양양 서핑 후기", None), "양양 서핑 후기.mp4")

    def test_presign_sets_attachment_with_utf8_name(self):
        with mock.patch.object(render_files, "s3_client") as s3:
            render_files.presign("renders/files/r1.mp4", "양양.mp4")
        params = s3.return_value.generate_presigned_url.call_args.kwargs["Params"]
        self.assertIn("attachment", params["ResponseContentDisposition"])
        self.assertIn("filename*=UTF-8''", params["ResponseContentDisposition"])
        self.assertLessEqual(s3.return_value.generate_presigned_url.call_args.kwargs["ExpiresIn"], 3600)


class TestWebhookMirrors(unittest.TestCase):
    ENV = {"WEBHOOK_BASE_URL": "https://api", "WEBHOOK_SECRET": "s3cret"}

    def setUp(self):
        import api.blog as blog
        self.blog = blog
        p = mock.patch.dict(os.environ, self.ENV, clear=False); p.start(); self.addCleanup(p.stop)

    def _run(self, status, mirror_result=None, mirror_side=None):
        with mock.patch.object(self.blog, "_fetch_render",
                               return_value={"id": "r1", "status": status, "url": "https://c/r1.mp4"}), \
             mock.patch.object(self.blog.render_store, "get", return_value={}), \
             mock.patch.object(self.blog.render_store, "update_result") as up, \
             mock.patch.object(self.blog.render_files, "mirror",
                               return_value=mirror_result, side_effect=mirror_side) as mi, \
             mock.patch.object(self.blog, "alert"):
            got = self.blog.creatomate_webhook({"id": "r1"}, token="s3cret")
        return got, up, mi

    def test_success_is_copied_and_recorded(self):
        _, up, mi = self._run("succeeded", {"video_key": "renders/files/r1.mp4", "video_bytes": 3})
        mi.assert_called_once_with("r1", "https://c/r1.mp4")
        self.assertEqual(up.call_args.kwargs.get("video_key"), "renders/files/r1.mp4")

    def test_failed_render_is_not_copied(self):
        _, _, mi = self._run("failed")
        mi.assert_not_called()

    def test_copy_failure_keeps_webhook_ok(self):
        got, up, _ = self._run("succeeded", None)
        self.assertEqual(got, {"status": "ok"})
        self.assertEqual(up.call_count, 1, "결과 기록은 남고, 파일 필드 갱신만 빠진다")


class TestMyRenders(unittest.TestCase):
    def setUp(self):
        import api.blog as blog
        self.blog = blog
        p = mock.patch.object(render_files, "presign", side_effect=lambda k, n=None: f"signed:{k}:{n}")
        p.start(); self.addCleanup(p.stop)

    def _call(self, records, fetch=None, mirror=None):
        with mock.patch.object(self.blog.render_store, "list_for_user", return_value=records), \
             mock.patch.object(self.blog.render_store, "update_result") as up, \
             mock.patch.object(self.blog, "_fetch_render", side_effect=fetch or (lambda rid: {})) as f, \
             mock.patch.object(self.blog.render_files, "mirror",
                               side_effect=mirror or (lambda rid, url: None)) as mi:
            got = self.blog.my_renders(user={"id": "u1"})["renders"]
        return got, up, f, mi

    def test_stored_video_uses_presigned_s3(self):
        got, *_ = self._call([_rec("r1", video_key="renders/files/r1.mp4")])
        self.assertEqual(got[0]["state"], "ready")
        self.assertTrue(got[0]["video_url"].startswith("signed:renders/files/r1.mp4"))
        self.assertTrue(got[0]["download_url"].endswith(":제목.mp4"))

    def test_unstored_recent_video_is_copied_now(self):
        got, _, _, mi = self._call(
            [_rec("r1")], mirror=lambda rid, url: {"video_key": f"renders/files/{rid}.mp4"})
        mi.assert_called_once()
        self.assertTrue(got[0]["video_url"].startswith("signed:"))

    def test_unstored_and_copy_failed_falls_back_to_creatomate(self):
        got, *_ = self._call([_rec("r1")])
        self.assertEqual(got[0]["state"], "ready")
        self.assertEqual(got[0]["video_url"], "https://creatomate/r1.mp4")

    def test_older_than_30_days_unstored_is_expired(self):
        got, _, _, mi = self._call([_rec("r1", age=31 * DAY)])
        self.assertEqual(got[0]["state"], "expired")
        self.assertIsNone(got[0]["video_url"])
        mi.assert_not_called()              # 이미 사라진 파일을 받으러 가지 않는다

    def test_stale_making_is_refreshed(self):
        got, up, f, _ = self._call(
            [_rec("r1", status="rendering", age=600, url=None)],
            fetch=lambda rid: {"status": "succeeded", "url": "https://c/r1.mp4", "duration": 20})
        f.assert_called_once_with("r1")
        self.assertEqual(up.call_args_list[0].args[:2], ("r1", "succeeded"))
        self.assertEqual(got[0]["state"], "ready")

    def test_fresh_making_is_left_alone(self):
        """방금 접수한 건 평소대로 웹훅을 기다린다 — 목록 열 때마다 물어보지 않는다."""
        got, _, f, _ = self._call([_rec("r1", status="planned", age=30, url=None)])
        f.assert_not_called()
        self.assertEqual(got[0]["state"], "making")

    def test_repairs_are_capped(self):
        recs = [_rec(f"r{i}", status="rendering", age=600, url=None) for i in range(10)]
        _, _, f, _ = self._call(recs)
        self.assertEqual(f.call_count, self.blog.MAX_REPAIRS_PER_CALL)

    def test_refresh_error_does_not_break_list(self):
        def boom(rid): raise RuntimeError("creatomate down")
        got, *_ = self._call([_rec("r1", status="rendering", age=600, url=None)], fetch=boom)
        self.assertEqual(got[0]["state"], "making")

    def test_failed_render_shown_as_failed(self):
        got, *_ = self._call([_rec("r1", status="failed", url=None)])
        self.assertEqual(got[0]["state"], "failed")

    def test_no_internal_fields_leak(self):
        got, *_ = self._call([_rec("r1", video_key="renders/files/r1.mp4", video_bytes=3)])
        for k in ("user_id", "video_key", "video_bytes", "url"):
            self.assertNotIn(k, got[0])


if __name__ == "__main__":
    unittest.main()
