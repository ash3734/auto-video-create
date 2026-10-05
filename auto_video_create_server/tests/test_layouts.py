"""화면 배치(레이아웃) — 단위 테스트 (2026-10-05, 백로그 5-2).

지키려는 것:
  · 장면 수 4~8 × prod/test 템플릿 JSON 10개가 전부 있고, 장면 수와 구조가 맞는다
  · prod 에는 워터마크가 없다 (test 템플릿이 prod 로 나가면 고객 영상에 워터마크가 찍힌다)
  · 우리 코드가 값을 넣는 요소 이름(image/video/audio N, 자막, 제목, 배경음악)이 다 있다
  · 렌더 요청이 template_id 가 아니라 source 로 나가고, 파일이 없으면 template_id 로 돌아간다
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import layouts  # noqa: E402
from services.music import BGM_ELEMENT  # noqa: E402
from services.scene_counts import ALLOWED_SCENE_COUNTS, SCENE_COUNT_CONFIG  # noqa: E402

WATERMARK_TEXT = "AUTO SHORT FORM AI"


def _names(el, out=None):
    out = [] if out is None else out
    for e in el.get("elements") or []:
        if e.get("name"):
            out.append(e["name"])
        _names(e, out)
    return out


def _load(env, n):
    with open(os.path.join(layouts.SOURCES_DIR, "letterbox", f"{env}_{n}.json"), encoding="utf-8") as f:
        return json.load(f)


class TestLetterboxSnapshots(unittest.TestCase):
    def test_all_ten_exist_and_match_config(self):
        """파일의 템플릿 ID 가 scene_counts 설정과 같아야 한다 — 다른 템플릿을 복사해 두면 안 된다."""
        for n in ALLOWED_SCENE_COUNTS:
            for env in ("prod", "test"):
                rec = _load(env, n)
                self.assertEqual(rec["template_id"], SCENE_COUNT_CONFIG[n][f"template_id_{env}"], (env, n))

    def test_every_element_we_fill_exists(self):
        """modifications 가 가리키는 이름이 없으면 Creatomate 가 400 을 낸다 — 영상 생성 실패."""
        for n in ALLOWED_SCENE_COUNTS:
            for env in ("prod", "test"):
                names = set(_names(_load(env, n)["source"]))
                need = {"title", BGM_ELEMENT}
                for i in range(1, n + 1):
                    need |= {f"image{i}", f"video{i}", f"audio{i}"}
                need |= {f"Subtitles-{s}" for s in SCENE_COUNT_CONFIG[n]["subtitle_suffixes"]}
                self.assertFalse(need - names, f"{env}_{n} 에 없는 요소: {need - names}")

    def test_no_extra_scene_slots(self):
        """5장면 템플릿에 image6 이 있으면 빈 장면이 영상에 끼어든다."""
        for n in ALLOWED_SCENE_COUNTS:
            names = set(_names(_load("prod", n)["source"]))
            self.assertNotIn(f"image{n + 1}", names)

    def test_prod_has_no_watermark(self):
        for n in ALLOWED_SCENE_COUNTS:
            self.assertNotIn(WATERMARK_TEXT, json.dumps(_load("prod", n)["source"], ensure_ascii=False), n)

    def test_test_has_watermark(self):
        """test 결과물이 고객 영상으로 오인되지 않게 워터마크가 있어야 한다."""
        for n in ALLOWED_SCENE_COUNTS:
            self.assertIn(WATERMARK_TEXT, json.dumps(_load("test", n)["source"], ensure_ascii=False), n)

    def test_vertical_720x1280(self):
        for n in ALLOWED_SCENE_COUNTS:
            src = _load("prod", n)["source"]
            self.assertEqual((src["width"], src["height"]), (720, 1280))


class TestGetSource(unittest.TestCase):
    def test_env_picks_prod_or_test(self):
        with mock.patch.dict(os.environ, {"ENV": "production"}):
            prod = json.dumps(layouts.get_source("letterbox", 5), ensure_ascii=False)
        with mock.patch.dict(os.environ, {"ENV": "test"}):
            test = json.dumps(layouts.get_source("letterbox", 5), ensure_ascii=False)
        self.assertNotIn(WATERMARK_TEXT, prod)
        self.assertIn(WATERMARK_TEXT, test)

    def test_unknown_layout_falls_back_to_default(self):
        self.assertEqual(layouts.get_source("없는배치", 5), layouts.get_source(layouts.DEFAULT_LAYOUT, 5))

    def test_returns_a_copy(self):
        """한 요청에서 고친 값이 다음 요청에 남으면 남의 영상이 섞인다."""
        a = layouts.get_source("letterbox", 5)
        a["width"] = 1
        self.assertEqual(layouts.get_source("letterbox", 5)["width"], 720)

    def test_missing_file_returns_none(self):
        layouts._load.cache_clear()
        with mock.patch.object(layouts, "SOURCES_DIR", "/nonexistent"):
            self.assertIsNone(layouts.get_source("letterbox", 5))
        layouts._load.cache_clear()


class TestRenderPayload(unittest.TestCase):
    def _render(self, source):
        import services.create_creatomate_video as c
        with mock.patch.object(c, "get_template_id", return_value="tpl-id"), \
             mock.patch.object(c, "get_source", return_value=source), \
             mock.patch.object(c, "alert") as al, \
             mock.patch.object(c, "requests") as rq:
            rq.post.return_value = mock.Mock(status_code=202, json=lambda: [{"id": "r1"}], text="")
            c.create_creatomate_video(["a.mp3"], ["대본"], title="제목", user_id=None, scene_count=5,
                                      webhook_url="https://cb", metadata="u1", **{"image1.source": "x"})
        return json.loads(rq.post.call_args.kwargs["data"]), al

    def test_sends_source_not_template_id(self):
        payload, al = self._render({"width": 720, "elements": []})
        self.assertEqual(payload["source"], {"width": 720, "elements": []})
        self.assertNotIn("template_id", payload)
        self.assertEqual(payload["modifications"]["image1.source"], "x")
        self.assertEqual(payload["modifications"]["title.text"], "제목")
        self.assertEqual(payload["webhook_url"], "https://cb")
        al.assert_not_called()

    def test_falls_back_to_template_id_and_alerts(self):
        payload, al = self._render(None)
        self.assertEqual(payload["template_id"], "tpl-id")
        self.assertNotIn("source", payload)
        al.assert_called_once()


if __name__ == "__main__":
    unittest.main()
