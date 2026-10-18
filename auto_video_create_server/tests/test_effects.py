"""화면 효과 — 사진 움직임 · 장면 전환 (2026-10-18, 백로그 3-7).

지키려는 것:
  · 안 고르면 템플릿 JSON 이 한 글자도 안 바뀐다 (기존 결과물 유지)
  · 전환이 장면을 겹치지 않는다 — 겹치면 나레이션이 동시에 들린다
  · 첫 장면에는 전환을 넣지 않는다 (영상 시작)
  · 영상 장면에는 확대를 넣지 않는다
  · 마지막 장면의 끝 페이드가 그대로 남는다
  · 기본·흐린 배경 배치 모두에 똑같이 붙는다
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import effects, layouts  # noqa: E402


def _scenes(src):
    return [e for e in src["elements"] if (e.get("name") or "").startswith("composition_") and e["name"][-1].isdigit()]


def _child(comp, name):
    return next(e for e in comp["elements"] if e.get("name") == name)


class TestApply(unittest.TestCase):
    def setUp(self):
        self.src = layouts.get_source("letterbox", 5)

    def test_default_changes_nothing(self):
        for m, t in ((None, None), ("none", "none"), ("모름", "x")):
            self.assertEqual(json.dumps(effects.apply(self.src, m, t)), json.dumps(self.src), (m, t))

    def test_does_not_mutate_input(self):
        before = json.dumps(self.src)
        effects.apply(self.src, "zoom", "punch")
        self.assertEqual(json.dumps(self.src), before)

    def test_zoom_on_photo_scenes_only(self):
        v = {"image1.visible": "true", "image2.visible": "false", "video2.visible": "true"}
        out = _scenes(effects.apply(self.src, "zoom", "none", v))
        self.assertTrue(any(a["type"] == "scale" for a in _child(out[0], "image1").get("animations", [])))
        self.assertFalse(_child(out[1], "image2").get("animations"), "영상 장면에는 확대를 넣지 않는다")

    def test_no_transition_on_first_scene(self):
        out = _scenes(effects.apply(self.src, "none", "fade"))
        first_types = [a["type"] for a in out[0].get("animations", [])]
        self.assertNotIn("fade", first_types)
        for comp in out[1:]:
            self.assertEqual(comp["animations"][0]["type"], "fade")

    def test_transitions_never_overlap_scenes(self):
        """transition: true 는 두 장면을 겹쳐 나레이션이 동시에 들린다 — 쓰지 않는다."""
        for t in ("fade", "punch"):
            out = effects.apply(self.src, "zoom", t)
            self.assertNotIn('"transition": true', json.dumps(out), t)

    def test_last_scene_keeps_end_fade(self):
        out = _scenes(effects.apply(self.src, "zoom", "punch"))
        ends = [a for a in out[-1]["animations"] if a.get("time") == "end"]
        self.assertTrue(ends, "마지막 장면 끝 페이드가 사라지면 영상이 뚝 끊긴다")

    def test_works_on_blur_layout_too(self):
        with mock.patch.dict(os.environ, {"ENV": "production"}):
            src = layouts.get_source("blur_fill", 6)
        out = _scenes(effects.apply(src, "zoom", "punch", {f"image{i}.visible": "true" for i in range(1, 7)}))
        self.assertEqual(len(out), 6)
        for i, comp in enumerate(out, 1):
            self.assertTrue(_child(comp, f"image{i}").get("animations"))

    def test_slide_was_removed(self):
        """밀어서는 검은 띠가 보여 뺐다 (2026-10-18). 예전 화면이 보내도 효과 없음으로 흐른다."""
        self.assertNotIn("slide", effects.TRANSITIONS)
        self.assertEqual(effects.normalize_transition("slide"), "none")

    def test_zoom_is_modest(self):
        """확대가 크면 사진 가장자리가 많이 잘린다 (사진 안 자르기 원칙)."""
        self.assertLessEqual(int(effects.ZOOM_END.rstrip("%")), 110)


class TestWiring(unittest.TestCase):
    def test_render_applies_effects(self):
        import services.create_creatomate_video as c
        with mock.patch.object(c, "get_template_id", return_value="tpl"), \
             mock.patch.object(c, "requests") as rq:
            rq.post.return_value = mock.Mock(status_code=202, json=lambda: [{"id": "r1"}], text="")
            c.create_creatomate_video(["a.mp3"], ["대본"], title="t", user_id=None, scene_count=5,
                                      motion="zoom", transition="punch",
                                      **{"image1.source": "x", "image1.visible": "true"})
        payload = json.loads(rq.post.call_args.kwargs["data"])
        self.assertIn('"start_scale": "115%"', json.dumps(payload["source"]))

    def test_api_listing_and_request(self):
        import api.blog as blog
        got = blog.get_effects()
        self.assertEqual([x["id"] for x in got["motions"] if x["is_default"]], ["none"])
        self.assertEqual([x["id"] for x in got["transitions"] if x["is_default"]], ["none"])
        req = blog.GenerateVideoRequest(title="t", scripts=["a"], sections=[])
        self.assertIsNone(req.motion)
        self.assertIsNone(req.transition)


if __name__ == "__main__":
    unittest.main()
