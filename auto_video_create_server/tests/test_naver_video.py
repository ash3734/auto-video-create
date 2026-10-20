"""네이버 본문 영상 추출 + 영상 자동 추천 (2026-10-20)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup  # noqa: E402

from crawler import naver_video  # noqa: E402
from services import layouts  # noqa: E402
from services.blog_shorts import _build_suggested_sections, video_target  # noqa: E402
from services.scene_media import video_slot_variables  # noqa: E402

VID = "95ECF89F5E29B1758F027E6A37A484B8FDA6"

# 2026-10-20 실제 고객 글의 구조를 줄인 것 — 빈 se-module-video 칸 + 데이터 스크립트
HTML = """
<div class="se-main-container">
  <div class="se-component se-video">
    <div class="se-module se-module-video" id="SE-1"></div>
    <script type="text/data" class="__se_module_data"
      data-module-v2='{"type": "v2_video", "id": "SE-1", "data": {"ctype": "video", "vid": "%s",
      "inkey": "V12abc", "thumbnail": "https://phinf.pstatic.net/x.jpg",
      "mediaMeta": {"@ctype":"mediaMeta","title":"썬쉐이드 수리","tags":[]}}}'></script>
  </div>
  <div class="se-component se-text"><!-- SE-TEXT { --><p>레일과 모터까지 점검합니다.</p>
    <script type="text/data" class="__se_module_data" data-module-v2='{"type": "v2_text", "data": {}}'></script>
  </div>
</div>
""" % VID

PLAY = {"videos": {"list": [
    {"source": "https://b01-kr-naver-vod.pstatic.net/a/%s/pd/480.mp4?_lsu_sa_=x" % VID,
     "encodingOption": {"height": 480}},
    {"source": "https://b01-kr-naver-vod.pstatic.net/a/%s/pd/1080.mp4?_lsu_sa_=x" % VID,
     "encodingOption": {"height": 1080}},
    {"source": "https://b01-kr-naver-vod.pstatic.net/a/%s/pd/720.mp4?_lsu_sa_=x" % VID,
     "encodingOption": {"height": 720}},
]}}


class TestFindModules(unittest.TestCase):
    def test_reads_vid_inkey_title_context(self):
        mods = naver_video.find_modules(BeautifulSoup(HTML, "html.parser"))
        self.assertEqual(len(mods), 1)
        m = mods[0]
        self.assertEqual((m["vid"], m["inkey"], m["title"]), (VID, "V12abc", "썬쉐이드 수리"))
        # 뒤따르는 본문 글이 단서가 된다 (스크립트 태그 안의 JSON 은 빼고)
        self.assertIn("레일과 모터", m["context"])
        self.assertNotIn("v2_text", m["context"])
        self.assertNotIn("SE-TEXT", m["context"])   # 에디터 주석은 글이 아니다

    def test_no_video_no_modules(self):
        soup = BeautifulSoup('<div><script class="__se_module_data" data-module-v2=\'{"type":"v2_image"}\'></script></div>',
                             "html.parser")
        self.assertEqual(naver_video.find_modules(soup), [])


class TestResolve(unittest.TestCase):
    def test_picks_720_and_keeps_inkey(self):
        resp = mock.Mock(json=lambda: PLAY, raise_for_status=lambda: None)
        with mock.patch.object(naver_video.requests, "get", return_value=resp):
            url = naver_video.resolve(VID, "V12abc")
        self.assertIn("/720.mp4", url)
        self.assertIn("_lsu_sa_=x", url)
        self.assertIn("avc_inkey=V12abc", url)

    def test_failure_is_none(self):
        with mock.patch.object(naver_video.requests, "get", side_effect=RuntimeError("down")):
            self.assertIsNone(naver_video.resolve(VID, "k"))

    def test_resolve_all_drops_failures(self):
        mods = [{"vid": "A", "inkey": "1"}, {"vid": "B", "inkey": "2"}]
        with mock.patch.object(naver_video, "resolve", side_effect=lambda v, k: "u" if v == "A" else None):
            got = naver_video.resolve_all(mods)
        self.assertEqual([g["vid"] for g in got], ["A"])


class TestRefresh(unittest.TestCase):
    URL = "https://b01-kr-naver-vod.pstatic.net/a/%s/pd/720.mp4?_lsu_sa_=old&avc_inkey=V12abc" % VID

    def test_refresh_uses_vid_and_inkey(self):
        with mock.patch.object(naver_video, "resolve", return_value="fresh") as r:
            self.assertEqual(naver_video.refresh(self.URL), "fresh")
        r.assert_called_once_with(VID, "V12abc")

    def test_refresh_failure_keeps_url(self):
        with mock.patch.object(naver_video, "resolve", return_value=None):
            self.assertEqual(naver_video.refresh(self.URL), self.URL)

    def test_refresh_akamai_host(self):
        # Lambda 에서 받으면 이 주소가 온다 — 만료 시각이 박혀 있어 꼭 새로 받아야 한다
        url = ("https://a01-g-naver-vod.akamaized.net/blog/a/%s/pd/x.mp4"
               "?__gda__=1792502056_abc&in_out_flag=1&avc_inkey=K" % VID)
        with mock.patch.object(naver_video, "resolve", return_value="fresh") as r:
            self.assertEqual(naver_video.refresh(url), "fresh")
        r.assert_called_once_with(VID, "K")

    def test_other_hosts_untouched(self):
        with mock.patch.object(naver_video, "resolve") as r:
            self.assertEqual(naver_video.refresh("https://example.com/a.mp4"), "https://example.com/a.mp4")
        r.assert_not_called()


class TestSuggestedWithVideos(unittest.TestCase):
    IMGS = ["i0", "i1", "i2"]
    VIDS = ["v0", "v1"]

    def test_ai_picks_video_by_combined_number(self):
        # 목록: 사진 3장(0~2) 다음 영상(3, 4)
        got = _build_suggested_sections([3, 0, 1], self.IMGS, ["v0"])
        self.assertEqual(got[0], {"type": "video", "url": "v0"})
        self.assertEqual([g["url"] for g in got[1:]], ["i0", "i1"])

    def test_offered_images_shifts_video_numbers(self):
        # 사진 3장 중 2장만 보여줬으면 영상 번호는 2부터
        got = _build_suggested_sections([2, None], self.IMGS, self.VIDS, offered_images=2)
        self.assertEqual(got[0], {"type": "video", "url": "v0"})

    def test_free_slot_gets_video_first(self):
        # 장면 4개 → 영상 목표 2개. 빈 칸(AI 가 못 고른 칸)부터, 그다음 사진 칸
        got = _build_suggested_sections([0, None, 1, 2], self.IMGS, self.VIDS)
        self.assertEqual(got[1], {"type": "video", "url": "v0"})
        self.assertEqual(got[3], {"type": "video", "url": "v1"})   # 본문 순서 모르면 마지막 사진 칸
        self.assertEqual([got[0]["url"], got[2]["url"]], ["i0", "i1"])

    def test_replaces_photo_nearest_in_body(self):
        # AI 가 사진만 골랐다 → 본문에서 영상(위치 50)과 가장 가까운 사진(i1, 위치 45)의 칸을 바꾼다
        pos = {"i0": 10, "i1": 45, "i2": 90, "v0": 50}
        got = _build_suggested_sections([0, 1, 2], self.IMGS, ["v0"], positions=pos)
        self.assertEqual([g["url"] for g in got], ["i0", "v0", "i2"])

    def test_half_of_scenes_at_most(self):
        # 장면 5개 → 영상은 3개까지. AI 가 고른 사진 둘은 그대로
        vids = ["v0", "v1", "v2", "v3"]
        got = _build_suggested_sections([0, 1, None, None, None], self.IMGS, vids)
        self.assertEqual(sum(g["type"] == "video" for g in got), 3)
        self.assertEqual([got[0]["url"], got[1]["url"]], ["i0", "i1"])

    def test_ai_video_picks_count_toward_target(self):
        # AI 가 이미 영상 2개를 골랐으면(장면 3개 → 목표 2) 사진은 안 바꾼다
        got = _build_suggested_sections([3, 0, 4], self.IMGS, self.VIDS)
        self.assertEqual([g["url"] for g in got], ["v0", "i0", "v1"])

    def test_videos_fill_after_images_run_out(self):
        got = _build_suggested_sections([None] * 5, ["i0"], self.VIDS)
        # 영상 둘은 뒤쪽 빈 칸부터, 사진은 앞에서부터, 나머지는 AI 배경
        self.assertEqual([g["url"] for g in got], ["i0", None, None, "v1", "v0"])
        self.assertEqual(got[1]["type"], "default")

    def test_without_videos_same_as_before(self):
        got = _build_suggested_sections([None, 0], ["i0", "i1"])
        self.assertEqual(got, [{"type": "image", "url": "i1"}, {"type": "image", "url": "i0"}])


class TestVideoTarget(unittest.TestCase):
    def test_half_rounded_up_capped_by_videos(self):
        self.assertEqual([video_target(n, 9) for n in (4, 5, 8)], [2, 3, 4])
        self.assertEqual(video_target(8, 1), 1)
        self.assertEqual(video_target(5, 0), 0)


class TestVideoContext(unittest.TestCase):
    def test_text_before_and_after(self):
        soup = BeautifulSoup(
            "<div><p>칠리치즈 프라이즈를 주문했어요</p><!-- SE-TEXT { --><video src='a.mp4'></video>"
            "<p>짜잔</p></div>", "html.parser")
        ctx = naver_video.context_around(soup.find("video"))
        self.assertIn("칠리치즈 프라이즈", ctx)
        self.assertIn("짜잔", ctx)
        self.assertNotIn("SE-TEXT", ctx)


class TestVideoSlot(unittest.TestCase):
    def test_muted_and_not_cropped(self):
        v = video_slot_variables(3, "s")
        self.assertEqual(v["video3.volume"], "0%")
        self.assertEqual(v["video3.fit"], "contain")
        self.assertEqual((v["video3.visible"], v["image3.visible"]), ("true", "false"))

    def test_fullscreen_fills_videos(self):
        out = layouts.extra_modifications("fullscreen", {"video2.source": "s", "image1.source": "p"}, 2)
        self.assertEqual(out["video2.fit"], "cover")
        self.assertEqual(out["image1.fit"], "cover")


if __name__ == "__main__":
    unittest.main()
