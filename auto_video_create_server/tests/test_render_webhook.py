"""렌더 기록 + Creatomate 웹훅 — 단위 테스트 (2026-09-20).

지키려는 것:
  · 웹훅 주소에는 비밀 토큰이 붙고, 토큰이 틀리면 받지 않는다 (문서에 서명이 없다)
  · 웹훅 본문을 믿지 않는다 — Creatomate 재조회 결과만 저장한다
  · 기록 저장이 실패해도 영상 생성은 계속된다
  · webhook_url·metadata 는 modifications 에 섞이지 않는다
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import render_store, webhooks  # noqa: E402


ENV = {"WEBHOOK_BASE_URL": "https://api.example.com/test", "WEBHOOK_SECRET": "s3cret"}


class TestWebhookUrl(unittest.TestCase):
    def test_url_has_token(self):
        with mock.patch.dict(os.environ, ENV, clear=False):
            self.assertEqual(
                webhooks.webhook_url(),
                "https://api.example.com/test/api/blog/creatomate-webhook?token=s3cret",
            )

    def test_no_url_when_unconfigured(self):
        """설정이 없으면 웹훅을 요청하지 않는다 — 기존 폴링으로 동작."""
        for env in ({"WEBHOOK_BASE_URL": "", "WEBHOOK_SECRET": "s"},
                    {"WEBHOOK_BASE_URL": "https://x", "WEBHOOK_SECRET": ""}):
            with mock.patch.dict(os.environ, env, clear=False):
                self.assertIsNone(webhooks.webhook_url())

    def test_token_check(self):
        with mock.patch.dict(os.environ, ENV, clear=False):
            self.assertTrue(webhooks.token_ok("s3cret"))
            for bad in ("", "other", None, "S3CRET"):
                self.assertFalse(webhooks.token_ok(bad), repr(bad))

    def test_token_rejected_when_unconfigured(self):
        """비밀값이 없는 환경에서 빈 토큰으로 통과되면 누구나 호출할 수 있다."""
        with mock.patch.dict(os.environ, {"WEBHOOK_SECRET": ""}, clear=False):
            self.assertFalse(webhooks.token_ok(""))


class TestRenderStore(unittest.TestCase):
    def setUp(self):
        self.s3 = {}
        r = mock.patch.object(render_store, "_read", side_effect=lambda k: self.s3.get(k))
        w = mock.patch.object(render_store, "_write", side_effect=lambda k, v: self.s3.__setitem__(k, v))
        r.start(); w.start()
        self.addCleanup(mock.patch.stopall)

    def test_submitted_then_result(self):
        render_store.save_submitted("r1", "linkplc", title="제목", scene_count=8)
        render_store.update_result("r1", "succeeded", url="https://v/r1.mp4")
        rec = render_store.get("r1")
        self.assertEqual((rec["status"], rec["url"], rec["user_id"]),
                         ("succeeded", "https://v/r1.mp4", "linkplc"))
        self.assertEqual(rec["title"], "제목")

    def test_user_list_newest_first(self):
        for rid in ("r1", "r2", "r3"):
            render_store.save_submitted(rid, "ssonek")
        self.assertEqual([r["render_id"] for r in render_store.list_for_user("ssonek")],
                         ["r3", "r2", "r1"])

    def test_result_without_submit_record(self):
        """접수 기록이 없어도 결과는 남는다."""
        render_store.update_result("r9", "succeeded", url="u")
        self.assertEqual(render_store.get("r9")["status"], "succeeded")

    def test_save_failure_does_not_raise(self):
        """기록 실패가 영상 생성을 막으면 안 된다 — 크레딧은 이미 빠졌다."""
        with mock.patch.object(render_store, "_write", side_effect=RuntimeError("S3 다운")):
            self.assertFalse(render_store.save_submitted("r1", "u1"))
            self.assertFalse(render_store.update_result("r1", "succeeded"))

    def test_other_users_records_not_listed(self):
        render_store.save_submitted("r1", "a")
        render_store.save_submitted("r2", "b")
        self.assertEqual([r["render_id"] for r in render_store.list_for_user("a")], ["r1"])


class TestWebhookEndpoint(unittest.TestCase):
    def setUp(self):
        import api.blog as blog
        self.blog = blog
        self.env = mock.patch.dict(os.environ, ENV, clear=False); self.env.start()
        self.addCleanup(self.env.stop)

    def test_bad_token_rejected(self):
        from fastapi import HTTPException
        with mock.patch.object(self.blog.render_store, "update_result") as up:
            with self.assertRaises(HTTPException) as cm:
                self.blog.creatomate_webhook({"id": "r1", "status": "succeeded"}, token="wrong")
        self.assertEqual(cm.exception.status_code, 403)
        up.assert_not_called()

    def test_body_is_not_trusted(self):
        """본문이 succeeded 라고 해도, 재조회 결과가 진짜다."""
        real = {"id": "r1", "status": "failed", "error_message": "boom"}
        with mock.patch.object(self.blog, "_fetch_render", return_value=real), \
             mock.patch.object(self.blog.render_store, "update_result") as up, \
             mock.patch.object(self.blog, "alert"):
            self.blog.creatomate_webhook({"id": "r1", "status": "succeeded",
                                          "url": "https://공격자/가짜.mp4"}, token="s3cret")
        self.assertEqual(up.call_args.args[1], "failed")
        self.assertIsNone(up.call_args.kwargs.get("url"))

    def _webhook_with(self, status, waited):
        """지연 시간을 정해 웹훅을 한 번 처리하고, alert 목 객체를 돌려준다."""
        rec = {"render_id": "r1", "user_id": "linkplc", "submitted_at": "x", "title": "제목"}
        with mock.patch.object(self.blog, "_fetch_render",
                               return_value={"id": "r1", "status": status, "duration": 25.0}), \
             mock.patch.object(self.blog.render_store, "get", return_value=rec), \
             mock.patch.object(self.blog.render_store, "elapsed_seconds", return_value=waited), \
             mock.patch.object(self.blog.render_store, "update_result"), \
             mock.patch.object(self.blog, "alert") as a:
            self.blog.creatomate_webhook({"id": "r1"}, token="s3cret")
        return a

    def test_slow_success_alerts_admin(self):
        """평소(20~30초)보다 크게 늦은 완료는 관리자에게 알린다."""
        a = self._webhook_with("succeeded", 900)
        a.assert_called_once()
        self.assertEqual(a.call_args.kwargs["waited_sec"], 900)
        self.assertEqual(a.call_args.kwargs["user"], "linkplc")

    def test_normal_success_does_not_alert(self):
        """정상 속도까지 알리면 하루 수십 통이 되어 알림을 안 보게 된다."""
        self._webhook_with("succeeded", 25).assert_not_called()

    def test_threshold_is_two_minutes(self):
        from services import webhooks as w
        self.assertEqual(w.SLOW_SECONDS, 120)
        self._webhook_with("succeeded", w.SLOW_SECONDS - 1).assert_not_called()
        self._webhook_with("succeeded", w.SLOW_SECONDS).assert_called_once()

    def test_failed_render_alerts_even_when_fast(self):
        self._webhook_with("failed", 10).assert_called_once()

    def test_failed_render_alerts(self):
        with mock.patch.object(self.blog, "_fetch_render",
                               return_value={"id": "r1", "status": "failed"}), \
             mock.patch.object(self.blog.render_store, "update_result"), \
             mock.patch.object(self.blog, "alert") as a:
            self.blog.creatomate_webhook({"id": "r1"}, token="s3cret")
        a.assert_called_once()

    def test_poll_uses_saved_result_without_calling_creatomate(self):
        saved = {"render_id": "r1", "status": "succeeded", "url": "https://v/r1.mp4"}
        with mock.patch.object(self.blog.render_store, "get", return_value=saved), \
             mock.patch.object(self.blog, "_fetch_render") as f:
            got = self.blog.poll_video("r1", user={"id": "linkplc"})
        f.assert_not_called()
        self.assertEqual(got["url"], "https://v/r1.mp4")

    def test_poll_falls_back_to_creatomate(self):
        """웹훅이 안 온 건은 기존처럼 직접 물어본다."""
        with mock.patch.object(self.blog.render_store, "get", return_value=None), \
             mock.patch.object(self.blog, "_fetch_render",
                               return_value={"status": "transcribing"}) as f, \
             mock.patch.object(self.blog.render_store, "update_result") as up:
            got = self.blog.poll_video("r1", user={"id": "linkplc"})
        f.assert_called_once()
        up.assert_not_called()          # 아직 결과가 아니면 기록하지 않는다
        self.assertEqual(got["status"], "transcribing")


class TestCreatePayload(unittest.TestCase):
    def test_webhook_fields_are_not_modifications(self):
        """modifications 에 섞이면 Creatomate 가 그런 요소를 못 찾아 400 을 낸다."""
        import services.create_creatomate_video as c
        with mock.patch.object(c, "get_template_id", return_value="tpl"), \
             mock.patch.object(c, "check_user_credits", return_value=True), \
             mock.patch.object(c, "requests") as rq:
            rq.post.return_value = mock.Mock(status_code=202, json=lambda: [{"id": "r1"}], text="")
            c.create_creatomate_video(["a.mp3"], ["대본"], title="제목", user_id=None,
                                      scene_count=4, webhook_url="https://cb?token=x",
                                      metadata="linkplc")
        import json as _json
        payload = _json.loads(rq.post.call_args.kwargs["data"])
        self.assertEqual(payload["webhook_url"], "https://cb?token=x")
        self.assertEqual(payload["metadata"], "linkplc")
        self.assertNotIn("webhook_url", payload["modifications"])
        self.assertNotIn("metadata", payload["modifications"])


if __name__ == "__main__":
    unittest.main()
