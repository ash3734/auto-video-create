"""AI 기본 배경 — 단위 테스트 (2026-09-20).

배경: `dall-e-3` 가 OpenAI 에서 내려가 모든 호출이 400 으로 실패했고, fallback 인
단색 배경이 나가 **AI 배경 자리가 늘 하얀 화면**이었다. 캐시 폴더는 내내 비어 있었다.
실패해도 조용히 fallback 으로 넘어가는 구조라 아무도 몰랐다.

그래서 세 가지를 못 박는다.
  1. 응답이 b64_json 으로 와도 이미지를 저장한다 (gpt-image 계열의 형식)
  2. 세로 크기로 요청한다 (영상이 720×1280 세로다)
  3. 모델·크기가 캐시 키에 들어간다 (모델을 바꿨는데 옛 이미지를 쓰면 의미가 없다)
"""
import base64
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import ai_background as bg  # noqa: E402

PNG = base64.b64encode(b"\x89PNG_fake").decode()


def _fake_client(item):
    client = mock.Mock()
    client.images.generate.return_value = mock.Mock(data=[item])
    return client


class TestGenerate(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False)
        self.env.start(); self.addCleanup(self.env.stop)
        self.exists = mock.patch.object(bg, "_exists_in_s3", return_value=False)
        self.exists.start(); self.addCleanup(self.exists.stop)
        self.upload = mock.patch.object(bg, "_upload_png_to_s3")
        self.up = self.upload.start(); self.addCleanup(self.upload.stop)

    def test_b64_response_is_saved(self):
        """gpt-image 계열은 url 이 아니라 b64_json 으로 준다."""
        item = mock.Mock(spec=["b64_json"]); item.b64_json = PNG
        with mock.patch.object(bg.openai, "OpenAI", return_value=_fake_client(item)):
            url = bg.generate_background_for_slot("바다에서 서핑을 배웠어요", 0)
        self.assertNotEqual(url, bg.FALLBACK_URL)
        self.up.assert_called_once()
        self.assertEqual(self.up.call_args.args[1], base64.b64decode(PNG))

    def test_url_response_still_works(self):
        """옛 형식(url)으로 오더라도 받아 둔다."""
        item = mock.Mock(spec=["url"]); item.url = "https://img/x.png"
        with mock.patch.object(bg.openai, "OpenAI", return_value=_fake_client(item)), \
             mock.patch.object(bg.requests, "get", return_value=mock.Mock(content=b"PNG")):
            url = bg.generate_background_for_slot("대본", 1)
        self.assertNotEqual(url, bg.FALLBACK_URL)

    def test_empty_response_falls_back(self):
        """b64 도 url 도 없으면 fallback — 단, 터지지는 않는다."""
        item = mock.Mock(spec=[])
        with mock.patch.object(bg.openai, "OpenAI", return_value=_fake_client(item)), \
             mock.patch.object(bg, "alert"):
            self.assertEqual(bg.generate_background_for_slot("대본", 2), bg.FALLBACK_URL)

    def test_failure_raises_alert(self):
        """조용히 fallback 으로 넘어가서 몇 주 동안 하얀 화면이 나갔다. 이제는 알린다."""
        with mock.patch.object(bg.openai, "OpenAI", side_effect=RuntimeError("model does not exist")), \
             mock.patch.object(bg, "alert") as a:
            bg.generate_background_for_slot("대본", 0)
        a.assert_called_once()
        self.assertEqual(a.call_args.args[0], "ai_background")

    def test_requests_portrait_size(self):
        """정사각형으로 만들면 세로 영상에서 좌우가 잘린다."""
        item = mock.Mock(spec=["b64_json"]); item.b64_json = PNG
        client = _fake_client(item)
        with mock.patch.object(bg.openai, "OpenAI", return_value=client):
            bg.generate_background_for_slot("대본", 3)
        kwargs = client.images.generate.call_args.kwargs
        w, h = kwargs["size"].split("x")
        self.assertGreater(int(h), int(w), f"세로가 더 길어야 한다: {kwargs['size']}")
        self.assertEqual(kwargs["model"], bg.IMAGE_MODEL)

    def test_model_is_not_a_retired_one(self):
        """dall-e-3 는 내려갔고, gpt-image-1/1.5 도 2026 년 안에 종료된다."""
        self.assertNotIn(bg.IMAGE_MODEL, ("dall-e-3", "dall-e-2", "gpt-image-1", "gpt-image-1.5"))

    def test_cache_key_includes_model_and_size(self):
        """모델을 바꿨는데 옛 모델로 만든 이미지를 그대로 쓰면 바꾼 의미가 없다."""
        seen = []
        item = mock.Mock(spec=["b64_json"]); item.b64_json = PNG
        with mock.patch.object(bg.openai, "OpenAI", return_value=_fake_client(item)), \
             mock.patch.object(bg, "_public_url", side_effect=lambda k: seen.append(k) or k):
            bg.generate_background_for_slot("같은 대본", 0)
            with mock.patch.object(bg, "IMAGE_MODEL", "gpt-image-9"):
                bg.generate_background_for_slot("같은 대본", 0)
        self.assertNotEqual(seen[0], seen[1], "모델이 달라지면 캐시 키도 달라져야 한다")

    def test_prompt_carries_scene_text(self):
        """장면 내용이 안 들어가면 모든 장면이 같은 그림이 된다."""
        item = mock.Mock(spec=["b64_json"]); item.b64_json = PNG
        client = _fake_client(item)
        with mock.patch.object(bg.openai, "OpenAI", return_value=client):
            bg.generate_background_for_slot("양양에서 서핑을 배웠어요", 0)
        self.assertIn("양양에서 서핑", client.images.generate.call_args.kwargs["prompt"])

    def test_prompt_asks_for_illustration_not_photo(self):
        """사진처럼 만들면 가보지도 않은 가게의 가짜 사진이 후기 영상에 들어간다.

        "AI가 지어낸 게 아니라 창작자가 직접 찍은 사진으로 만든다"는 제품의 약속과
        정면으로 부딪히는 지점이라, 프롬프트에서 못 박는다.
        """
        item = mock.Mock(spec=["b64_json"]); item.b64_json = PNG
        client = _fake_client(item)
        with mock.patch.object(bg.openai, "OpenAI", return_value=client):
            bg.generate_background_for_slot("화양동 매장이 넓고 직원분들이 친절했어요", 0)
        prompt = client.images.generate.call_args.kwargs["prompt"]
        self.assertIn("일러스트", prompt)
        self.assertIn("사진처럼 보이지 않게", prompt)
        self.assertNotIn("추상", prompt)   # 추상 배경은 내용과 무관한 벽지가 된다

    def test_cache_key_includes_prompt_version(self):
        """프롬프트를 바꿔도 캐시가 옛 그림을 돌려주면 바꾼 의미가 없다."""
        seen = []
        item = mock.Mock(spec=["b64_json"]); item.b64_json = PNG
        with mock.patch.object(bg.openai, "OpenAI", return_value=_fake_client(item)), \
             mock.patch.object(bg, "_public_url", side_effect=lambda k: seen.append(k) or k):
            bg.generate_background_for_slot("같은 대본", 0)
            with mock.patch.object(bg, "PROMPT_VERSION", "v99"):
                bg.generate_background_for_slot("같은 대본", 0)
        self.assertNotEqual(seen[0], seen[1])

    def test_cache_hit_skips_api(self):
        with mock.patch.object(bg, "_exists_in_s3", return_value=True), \
             mock.patch.object(bg.openai, "OpenAI") as cli:
            bg.generate_background_for_slot("대본", 0)
        cli.assert_not_called()



class TestPrefetchedBackgroundIsReused(unittest.TestCase):
    """선택 화면에서 미리 만든 배경은 영상 만들 때 다시 만들지 않는다.

    다시 만들면 돈이 두 번 나가고, 화면에서 본 것과 다른 그림이 나올 수도 있다.
    """

    def _default_section(self, url):
        import api.blog as blog
        return blog.SectionMedia(type="default", url=url)

    def test_slot_with_url_is_not_regenerated(self):
        import api.blog as blog
        sections = [self._default_section("https://s3/bg-preview.png"),
                    self._default_section(None)]
        pairs = [
            (i, "대본")
            for i, s in enumerate(sections)
            if s.type == "default" and not s.url
        ]
        self.assertEqual([i for i, _ in pairs], [1], "URL 이 있는 슬롯은 재생성 대상이 아니어야 한다")

    def test_endpoint_returns_urls_by_slot(self):
        import api.blog as blog
        req = blog.AiBackgroundRequest(slots=[{"slot": 0, "script": "첫 장면"},
                                              {"slot": 3, "script": "네 번째 장면"}])
        with mock.patch.object(blog, "generate_backgrounds_parallel",
                               return_value={0: "https://s3/a.png", 3: "https://s3/b.png"}) as g:
            got = blog.ai_backgrounds(req, user={"id": "linkplc"})
        self.assertEqual(got["backgrounds"], {"0": "https://s3/a.png", "3": "https://s3/b.png"})
        self.assertEqual(sorted(i for i, _ in g.call_args.args[0]), [0, 3])

    def test_endpoint_ignores_broken_slots(self):
        import api.blog as blog
        req = blog.AiBackgroundRequest(slots=[{"slot": "x", "script": "a"}, {"script": "b"}])
        with mock.patch.object(blog, "generate_backgrounds_parallel") as g:
            got = blog.ai_backgrounds(req, user={"id": "linkplc"})
        self.assertEqual(got["backgrounds"], {})
        g.assert_not_called()


if __name__ == "__main__":
    unittest.main()
