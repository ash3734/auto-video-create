"""맛집 정보카드 가게 정보 — 뽑기·전달 (2026-10-18)."""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import place_info  # noqa: E402


class TestExtract(unittest.TestCase):
    def _run(self, content=None, side=None):
        import openai
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
             mock.patch.object(openai, "OpenAI") as cli:
            if side:
                cli.return_value.chat.completions.create.side_effect = side
            else:
                cli.return_value.chat.completions.create.return_value = mock.Mock(
                    choices=[mock.Mock(message=mock.Mock(content=content))])
            got = place_info.extract_place("신논현 세광양대창 후기, 모둠 1인분 18,000원")
        return got, cli

    def test_parses_and_cleans(self):
        got, cli = self._run(json.dumps({"name": "세광양대창", "location": "신논현", "price": "모둠 18,000원", "x": 1}))
        self.assertEqual(got, {"name": "세광양대창", "location": "신논현", "price": "모둠 18,000원"})
        kw = cli.call_args.kwargs
        self.assertLessEqual(kw["timeout"], 20)
        self.assertEqual(kw["max_retries"], 0)

    def test_failure_gives_empty_fields(self):
        got, _ = self._run(side=TimeoutError("slow"))
        self.assertEqual(got, {"name": "", "location": "", "price": ""})

    def test_bad_json_gives_empty_fields(self):
        got, _ = self._run(content="가게는 세광양대창")
        self.assertEqual(got, {"name": "", "location": "", "price": ""})

    def test_empty_text_makes_no_call(self):
        import openai
        with mock.patch.object(openai, "OpenAI") as cli:
            self.assertEqual(place_info.extract_place("  "), {"name": "", "location": "", "price": ""})
        cli.assert_not_called()

    def test_prompt_forbids_making_things_up(self):
        self.assertIn("지어내지", place_info.PROMPT)


class TestWiring(unittest.TestCase):
    def test_endpoint_and_request(self):
        import api.blog as blog
        with mock.patch.object(blog, "extract_place", return_value={"name": "a", "location": "", "price": ""}):
            self.assertEqual(blog.place_info(blog.PlaceInfoRequest(text="글"), user={"id": "u"})["place"]["name"], "a")
        req = blog.GenerateVideoRequest(title="t", scripts=["a"], sections=[], place_name="가게")
        self.assertEqual(req.place_name, "가게")

    def test_render_puts_place_on_card(self):
        import services.create_creatomate_video as c
        with mock.patch.object(c, "get_template_id", return_value="tpl"), mock.patch.object(c, "requests") as rq:
            rq.post.return_value = mock.Mock(status_code=202, json=lambda: [{"id": "r1"}], text="")
            c.create_creatomate_video(["a.mp3"], ["대본"], title="t", user_id=None, scene_count=5, layout="info_card",
                                      place={"name": "세광양대창", "location": "신논현", "price": ""})
        mods = json.loads(rq.post.call_args.kwargs["data"])["modifications"]
        self.assertEqual(mods["place_name.text"], "세광양대창")
        self.assertNotIn("place_card.visible", mods)


if __name__ == "__main__":
    unittest.main()
