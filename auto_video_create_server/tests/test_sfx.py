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

    def test_choices_are_only_on_off(self):
        """유저는 켤지 말지만 정한다 — 소리 종류는 AI 가 고른다 (2026-10-19 PO)."""
        self.assertEqual([x["id"] for x in sfx.available_sounds()], ["none", "auto"])
        self.assertNotIn("cdn.pixabay.com", json.dumps(sfx.available_sounds()))


class TestAuto(unittest.TestCase):
    def setUp(self):
        self.src = layouts.get_source("letterbox", 5)
        p = mock.patch.object(sfx, "render_url", side_effect=lambda sid: f"https://s3/{sid}.mp3?sig")
        p.start(); self.addCleanup(p.stop)

    def _sounds(self, src):
        out = {}
        for c in src["elements"]:
            for e in c.get("elements") or []:
                if e.get("name") == "sfx":
                    out[c["name"]] = e["source"].split("/")[-1].split(".")[0]
        return out

    def test_follows_plan(self):
        got = self._sounds(sfx.apply(self.src, "auto", [None, "ding", None, "pop", None]))
        self.assertEqual(got, {"composition_2": "ding", "composition_4": "pop"})

    def test_no_plan_uses_fallback_rule(self):
        got = self._sounds(sfx.apply(self.src, "auto", None))
        self.assertEqual(set(got.values()), {"whoosh"})
        self.assertNotIn("composition_1", got)

    def test_outro_gets_closing_ding(self):
        v = {"image5.source": "x", "image5.visible": "true"}
        src = bookends.apply(self.src, "none", None, "comment", None, v)
        got = self._sounds(sfx.apply(src, "auto", [None, None, None, None, None]))
        self.assertEqual(got, {"composition_outro": "ding"})

    def test_clean_plan_rules(self):
        self.assertEqual(sfx.clean_plan(["ding", "pop", "x", None], 4), [None, "pop", None, None])  # 1번·모르는 값 제거
        full = sfx.clean_plan(["pop"] * 6, 6)
        self.assertLessEqual(sum(1 for x in full if x), 3)                                         # 절반까지
        self.assertEqual(sfx.clean_plan("garbage", 3), [None, None, None])

    def test_plan_sounds_uses_ai_and_falls_back(self):
        import openai
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), mock.patch.object(openai, "OpenAI") as cli:
            cli.return_value.chat.completions.create.return_value = mock.Mock(choices=[mock.Mock(
                message=mock.Mock(content=json.dumps({"sounds": ["none", "swipe", "none", "ding"]})))])
            self.assertEqual(sfx.plan_sounds(["a", "b", "c", "d"]), [None, "swipe", None, "ding"])
            self.assertLessEqual(cli.call_args.kwargs["timeout"], 10)
            cli.return_value.chat.completions.create.side_effect = TimeoutError("slow")
            self.assertEqual(sfx.plan_sounds(["a", "b", "c"]), sfx.default_plan(3))

    def test_old_fixed_sound_still_works(self):
        """예전 화면이 소리 이름을 보내도 깨지지 않는다 (2번 장면부터 장면마다)."""
        got = self._sounds(sfx.apply(self.src, "pop"))
        self.assertEqual(len(got), 4)


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
        self.assertIn("auto", [x["id"] for x in blog.get_effects()["sounds"]])
        with mock.patch.object(blog.sfx, "plan_sounds", return_value=[None, "ding"]) as ps:
            self.assertEqual(blog.sfx_plan(blog.SfxPlanRequest(scripts=["a", "b"]), user={"id": "u"})["plan"], [None, "ding"])
        ps.assert_called_once()


if __name__ == "__main__":
    unittest.main()
