"""첫 화면 문구 · 끝 화면 (2026-10-18, 백로그 3-6).

지키려는 것:
  · 안 고르면 템플릿 JSON 이 그대로 (기존 결과물 유지)
  · 첫 화면 문구는 장면을 밀지 않는다 (나레이션 시작이 늦어지면 쇼츠는 넘겨진다)
  · 끝 화면은 마지막 장면 바로 뒤, 같은 트랙 — 마지막 장면의 끝 페이드는 끝 화면으로 옮긴다
  · 유저 입력 문구는 길이·줄 수를 자른다
  · 제목 글꼴을 따른다
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import bookends, effects, layouts  # noqa: E402


def _names(src):
    return [e.get("name") for e in src["elements"]]


class TestApply(unittest.TestCase):
    def setUp(self):
        self.src = layouts.get_source("letterbox", 5)
        self.v = {"title.text": "양양 서핑 후기", "image5.source": "https://p/5.jpg", "image5.visible": "true"}

    def test_default_changes_nothing(self):
        for args in ((None, None, None, None), ("none", "x", "none", "y"), ("모름", None, "모름", None)):
            self.assertEqual(json.dumps(bookends.apply(self.src, *args, self.v)), json.dumps(self.src), args)

    def test_intro_title_uses_title_text_and_does_not_shift_scenes(self):
        out = bookends.apply(self.src, "title", None, "none", None, self.v)
        intro = next(e for e in out["elements"] if e.get("name") == "intro_text")
        self.assertEqual(intro["text"], "양양 서핑 후기")
        self.assertEqual(intro["time"], 0)
        self.assertLessEqual(intro["duration"], 2)
        # 장면 순서·개수는 그대로
        self.assertEqual([n for n in _names(out) if n != "intro_text"], _names(self.src))

    def test_intro_on_top_track(self):
        out = bookends.apply(self.src, "title", None, "none", None, self.v)
        intro = next(e for e in out["elements"] if e.get("name") == "intro_text")
        self.assertGreater(intro["track"], max(e.get("track") or 0 for e in self.src["elements"]))

    def test_empty_custom_intro_adds_nothing(self):
        out = bookends.apply(self.src, "custom", "   ", "none", None, self.v)
        self.assertNotIn("intro_text", _names(out))

    def test_outro_right_after_last_scene_same_track(self):
        out = bookends.apply(self.src, "none", None, "comment", None, self.v)
        names = _names(out)
        i = names.index("composition_outro")
        self.assertEqual(names[i - 1], "composition_5")
        last = out["elements"][i - 1]
        outro = out["elements"][i]
        self.assertEqual(outro["track"], last["track"])
        self.assertNotIn("time", outro, "time 이 있으면 장면 뒤에 이어 붙지 않는다")
        self.assertEqual(outro["duration"], bookends.OUTRO_SECONDS)

    def test_end_fade_moves_to_outro(self):
        """마지막 장면에 끝 페이드가 남으면 끝 화면 직전에 한 번 어두워진다."""
        out = bookends.apply(self.src, "none", None, "follow", None, self.v)
        last = next(e for e in out["elements"] if e.get("name") == "composition_5")
        self.assertFalse(any(a.get("time") == "end" for a in last.get("animations") or []))
        outro = next(e for e in out["elements"] if e.get("name") == "composition_outro")
        self.assertTrue(any(a.get("time") == "end" for a in outro["animations"]))

    def test_outro_background_is_last_photo_or_dark(self):
        out = bookends.apply(self.src, "none", None, "blog", None, self.v)
        outro = next(e for e in out["elements"] if e.get("name") == "composition_outro")
        self.assertEqual(outro["elements"][0]["source"], "https://p/5.jpg")
        v = dict(self.v, **{"image5.visible": "false"})                 # 마지막이 영상 장면
        out = bookends.apply(self.src, "none", None, "blog", None, v)
        outro = next(e for e in out["elements"] if e.get("name") == "composition_outro")
        self.assertEqual([e["name"] for e in outro["elements"]], ["outro_text"])

    def test_follows_title_font(self):
        v = dict(self.v, **{"title.font_family": "Black Han Sans", "title.fill_color": "#00ff00"})
        out = bookends.apply(self.src, "title", None, "comment", None, v)
        intro = next(e for e in out["elements"] if e.get("name") == "intro_text")
        self.assertEqual((intro["font_family"], intro["fill_color"]), ("Black Han Sans", "#00ff00"))

    def test_works_with_effects_and_blur_layout(self):
        with mock.patch.dict(os.environ, {"ENV": "production"}):
            src = layouts.get_source("blur_fill", 8)
        v = {f"image{i}.visible": "true" for i in range(1, 9)}
        out = bookends.apply(effects.apply(src, "zoom", "punch", v), "title", None, "comment", None, v)
        names = _names(out)
        self.assertEqual(names[names.index("composition_outro") - 1], "composition_8")

    def test_presets_fit_two_lines(self):
        """기본 문구 한 줄이 9자를 넘으면 세 줄로 접힌다 (2026-10-18 샘플)."""
        for k, o in bookends.OUTROS.items():
            for line in o["text"].split("\n"):
                self.assertLessEqual(len(line), 9, (k, line))


class TestCleanText(unittest.TestCase):
    def test_limits(self):
        self.assertEqual(bookends.clean_text("a\nb\nc"), "a\nb")
        self.assertEqual(len(bookends.clean_text("가" * 100)), bookends.MAX_TEXT)
        self.assertEqual(bookends.clean_text("  여러   칸\r\n  공백 "), "여러 칸\n공백")
        self.assertEqual(bookends.clean_text(None), "")


class TestWiring(unittest.TestCase):
    def test_render_applies_bookends(self):
        import services.create_creatomate_video as c
        with mock.patch.object(c, "get_template_id", return_value="tpl"), \
             mock.patch.object(c, "requests") as rq:
            rq.post.return_value = mock.Mock(status_code=202, json=lambda: [{"id": "r1"}], text="")
            c.create_creatomate_video(["a.mp3"], ["대본"], title="제목", user_id=None, scene_count=5,
                                      intro="title", outro="comment")
        names = [e.get("name") for e in json.loads(rq.post.call_args.kwargs["data"])["source"]["elements"]]
        self.assertIn("intro_text", names)
        self.assertIn("composition_outro", names)

    def test_api(self):
        import api.blog as blog
        got = blog.get_bookends()
        self.assertEqual([x["id"] for x in got["intros"] if x["is_default"]], ["none"])
        self.assertEqual([x["id"] for x in got["outros"] if x["is_default"]], ["none"])
        req = blog.GenerateVideoRequest(title="t", scripts=["a"], sections=[])
        self.assertIsNone(req.intro)
        self.assertIsNone(req.outro)


if __name__ == "__main__":
    unittest.main()
