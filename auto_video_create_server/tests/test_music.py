"""배경음악 선택 — 단위 테스트 (2026-09-27).

지키려는 것:
  · 안 고른 요청은 기존 그대로 (템플릿 기본 음악) — 구버전 화면과 기존 유저의 결과물
  · 목록에 없는 곡은 실리지 않는다 (임의 URL 주입 차단)
  · 음원 주소는 **만료되는** presigned URL 이다 (Pixabay 재배포 금지 조항)
  · 영구 공개 버킷에 두지 않는다
  · 우리 영상 길이(16~30초)보다 짧은 곡이 목록에 없다
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services import music  # noqa: E402

# 우리가 만드는 영상 중 가장 긴 편(8장면)의 넉넉한 상한.
LONGEST_VIDEO_SECONDS = 60


class TestCatalog(unittest.TestCase):
    def test_four_concepts_five_each(self):
        counts = {}
        for t in music.TRACKS:
            counts[t["concept"]] = counts.get(t["concept"], 0) + 1
        self.assertEqual(counts, {"bright": 5, "calm": 5, "upbeat": 5, "emotional": 5})

    def test_concept_ids_match_track_concepts(self):
        """화면은 CONCEPTS 로 탭을 그린다 — 어긋나면 곡이 안 보이는 탭이 생긴다."""
        self.assertEqual({c["id"] for c in music.CONCEPTS},
                         {t["concept"] for t in music.TRACKS})

    def test_ids_unique(self):
        ids = [t["id"] for t in music.TRACKS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_id_starts_with_concept(self):
        """S3 키가 id 그대로다 — 규칙이 깨지면 업로드 스크립트와 어긋난다."""
        for t in music.TRACKS:
            self.assertTrue(t["id"].startswith(t["concept"] + "-"), t["id"])

    def test_every_track_outlasts_our_videos(self):
        """영상보다 짧은 곡을 고르면 중간에 음악이 끊긴 채로 결과물이 나간다."""
        for t in music.TRACKS:
            self.assertGreater(t["seconds"], LONGEST_VIDEO_SECONDS, t["id"])

    def test_license_recorded_for_every_track(self):
        """이 파일이 곧 라이선스 기록이다 — 출처 없는 곡이 섞이면 안 된다."""
        for t in music.TRACKS:
            self.assertTrue(t["source_page"].startswith("https://pixabay.com/"), t["id"])
            self.assertEqual(t["license"], "Pixabay Content License")
            self.assertTrue(t["artist"])

    def test_none_id_is_not_a_track(self):
        """'음악 없음'이 곡 id 와 겹치면 고를 수 없는 곡이 생긴다."""
        self.assertFalse(music.is_allowed(music.NONE_ID))


class TestStorageIsPrivate(unittest.TestCase):
    def test_not_the_public_bucket(self):
        """auto-video-tts-files 는 s3:GetObject 가 `*` 에 열린 공개 버킷이다.

        거기에 올리면 주소가 곧 상시 음원 배포처가 되어 Pixabay 라이선스에 걸린다.
        """
        self.assertNotEqual(music.BUCKET, "auto-video-tts-files")

    def test_urls_are_presigned_and_expire(self):
        with mock.patch.object(music, "s3_client") as c:
            c.return_value.generate_presigned_url.return_value = "https://s3/x.mp3?sig"
            music.preview_url("bright-indie-fun")
            preview_expires = c.return_value.generate_presigned_url.call_args.kwargs["ExpiresIn"]
            music.render_url("bright-indie-fun")
            render_expires = c.return_value.generate_presigned_url.call_args.kwargs["ExpiresIn"]
        for e in (preview_expires, render_expires):
            self.assertGreater(e, 0)
            self.assertLessEqual(e, 3600, "만료가 길면 영구 공개 주소와 다를 바 없다")
        self.assertLess(preview_expires, render_expires,
                        "미리듣기는 렌더보다 짧게 — 화면에 뿌려지는 주소다")


class TestBgmVariables(unittest.TestCase):
    """Creatomate 에 실제로 넘어가는 값."""

    def test_no_selection_keeps_template_default(self):
        """구버전 화면은 bgm_id 를 안 보낸다 — 그 요청의 결과물이 바뀌면 안 된다."""
        for raw in (None, "", 0, [], {}):
            self.assertEqual(music.bgm_variables(raw), {}, repr(raw))

    def test_unknown_id_falls_back_to_default(self):
        """모르는 값에 영상 생성을 실패시키지 않는다 — 음악은 그럴 만한 사안이 아니다."""
        self.assertEqual(music.bgm_variables("남의-음원"), {})
        self.assertEqual(music.bgm_variables("https://공격자/음원.mp3"), {})

    def test_none_silences_the_track(self):
        v = music.bgm_variables(music.NONE_ID)
        self.assertEqual(v, {f"{music.BGM_ELEMENT}.volume": "0%"})

    def test_selected_track_sets_source(self):
        with mock.patch.object(music, "render_url", return_value="https://s3/t.mp3?sig"):
            v = music.bgm_variables("calm-midnight-forest")
        self.assertEqual(v, {f"{music.BGM_ELEMENT}.source": "https://s3/t.mp3?sig"})

    def test_element_name_matches_every_template(self):
        """Audio-6FR 은 4~8장면 템플릿 10개에 모두 같은 이름으로 있다."""
        self.assertEqual(music.BGM_ELEMENT, "Audio-6FR")

    def test_presign_failure_falls_back_to_default(self):
        """주소를 못 만들었을 때 무음으로 내보내는 것보다 기본 음악이 낫다."""
        with mock.patch.object(music, "render_url", return_value=None):
            self.assertEqual(music.bgm_variables("calm-midnight-forest"), {})

    def test_variables_do_not_collide_with_scene_slots(self):
        """장면 오디오(audio1..audio8)와 키가 겹치면 나레이션을 덮어쓴다."""
        keys = set(music.bgm_variables(music.NONE_ID))
        for i in range(1, 9):
            self.assertNotIn(f"audio{i}.source", keys)


class TestListingEndpoint(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(music, "preview_url", side_effect=lambda t: f"https://s3/{t}?sig")
        self.p.start(); self.addCleanup(self.p.stop)

    def test_shape(self):
        got = music.available_tracks()
        self.assertEqual(got["none_id"], music.NONE_ID)
        self.assertEqual(len(got["tracks"]), 20)
        self.assertEqual(len(got["concepts"]), 4)
        first = got["tracks"][0]
        self.assertEqual(set(first),
                         {"id", "concept", "title", "artist", "seconds", "license", "preview_url"})

    def test_listing_never_leaks_the_bucket_path(self):
        """곡 목록에 S3 키나 원본 CDN 주소를 실어 보내지 않는다."""
        import json
        blob = json.dumps(music.available_tracks(), ensure_ascii=False)
        self.assertNotIn(music.BUCKET, blob)
        self.assertNotIn("cdn.pixabay.com", blob)


class TestRequestWiring(unittest.TestCase):
    def test_generate_video_request_accepts_bgm_id(self):
        import api.blog as blog
        req = blog.GenerateVideoRequest(title="t", scripts=["a"], sections=[], bgm_id="upbeat-summer-pop")
        self.assertEqual(req.bgm_id, "upbeat-summer-pop")

    def test_bgm_id_is_optional(self):
        import api.blog as blog
        self.assertIsNone(blog.GenerateVideoRequest(title="t", scripts=["a"], sections=[]).bgm_id)


if __name__ == "__main__":
    unittest.main()
