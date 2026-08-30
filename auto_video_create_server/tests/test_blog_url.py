"""블로그 주소 해석 — 회귀 테스트 (2026-08-30).

세 가지 실제 사고를 고정한다.

1. **test 알람 (08-30 12:51)** — 유저가 `m.blog.naver.com/{아이디}`(블로그 홈)을 넣었다.
   크롤러가 본문을 못 찾아 ValueError → catch-all 이 장애 알람을 울렸다. 장애가 아니라
   주소를 잘못 넣은 것이다. 홈 주소와 글 주소를 구분할 수 있어야 이걸 가른다.

2. **호스트 부분 문자열 우회** — 예전 구현이 `"blog.naver.com" in host` 였다.
   `blog.naver.com.attacker.io/{남의아이디}` 가 통과해 "본인 블로그만" 규칙이
   무력화됐다. 유료 구독자만 호출할 수 있어도 규칙 자체가 뚫리는 건 다르다.

3. **구형 PostView 링크 차단** — 네이버가 실제로 주는
   `PostView.naver?blogId=X&logNo=Y` 형식에서 작성자를 'PostView.naver' 로 읽어,
   본인 글인데도 "등록된 블로그 주소가 아닙니다" 로 막혔다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CREATOMATE_API_KEY", "dummy")

from services.blog_url import parse_blog_ref, same_blog  # noqa: E402

REGISTERED = "https://m.blog.naver.com/auctionrun0643"


class TestHomeVsPost(unittest.TestCase):
    """1번 사고 — 알람을 울린 그 구분."""

    def test_blog_home_is_not_a_post(self):
        self.assertFalse(parse_blog_ref("https://m.blog.naver.com/auctionrun0643").is_post)

    def test_bare_domain_is_not_a_post(self):
        self.assertFalse(parse_blog_ref("https://m.blog.naver.com").is_post)

    def test_real_post_is_a_post(self):
        r = parse_blog_ref("https://blog.naver.com/auctionrun0643/224394764731")
        self.assertTrue(r.is_post)
        self.assertEqual(r.post_id, "224394764731")

    def test_mobile_post_is_a_post(self):
        self.assertTrue(parse_blog_ref("https://m.blog.naver.com/auctionrun0643/224394764731").is_post)

    def test_post_list_is_not_a_post(self):
        self.assertFalse(parse_blog_ref("https://blog.naver.com/PostList.naver?blogId=abc").is_post)

    def test_tistory_home_vs_post(self):
        self.assertFalse(parse_blog_ref("https://someone.tistory.com").is_post)
        self.assertTrue(parse_blog_ref("https://someone.tistory.com/12").is_post)

    def test_brunch_home_vs_post(self):
        self.assertFalse(parse_blog_ref("https://brunch.co.kr/@abc").is_post)
        self.assertTrue(parse_blog_ref("https://brunch.co.kr/@abc/10").is_post)


class TestHostSpoofing(unittest.TestCase):
    """2번 사고 — 부분 문자열 검사 우회."""

    def test_lookalike_host_rejected(self):
        for bad in (
            "https://blog.naver.com.attacker.io/auctionrun0643/1",
            "https://myblog.naver.com.example.org/auctionrun0643/1",
            "https://notblog.naver.com/auctionrun0643/1",
        ):
            self.assertEqual(parse_blog_ref(bad).platform, "", bad)
            self.assertFalse(same_blog(REGISTERED, bad), bad)

    def test_non_https_rejected(self):
        self.assertEqual(parse_blog_ref("ftp://blog.naver.com/a/1").platform, "")
        self.assertEqual(parse_blog_ref("javascript:alert(1)").platform, "")


class TestLegacyPostViewLink(unittest.TestCase):
    """3번 사고 — 네이버가 실제로 주는 구형 링크."""

    def test_author_and_post_read_from_query(self):
        r = parse_blog_ref(
            "https://blog.naver.com/PostView.naver?blogId=auctionrun0643&logNo=224394764731")
        self.assertEqual(r.platform, "naver")
        self.assertEqual(r.author, "auctionrun0643")
        self.assertEqual(r.post_id, "224394764731")
        self.assertTrue(r.is_post)

    def test_mobile_variant(self):
        r = parse_blog_ref(
            "https://m.blog.naver.com/PostView.naver?blogId=auctionrun0643&logNo=1")
        self.assertEqual(r.author, "auctionrun0643")

    def test_owner_can_use_legacy_link(self):
        self.assertTrue(same_blog(
            REGISTERED,
            "https://blog.naver.com/PostView.naver?blogId=auctionrun0643&logNo=1"))


class TestOwnership(unittest.TestCase):
    def test_own_blog_passes(self):
        for u in (
            "https://blog.naver.com/auctionrun0643/224394764731",
            "https://m.blog.naver.com/auctionrun0643/1",
            "https://blog.naver.com/AUCTIONRUN0643/1",   # 대문자도 본인이다
        ):
            self.assertTrue(same_blog(REGISTERED, u), u)

    def test_other_blog_blocked(self):
        for u in ("https://blog.naver.com/someoneelse/1",
                  "https://other.tistory.com/1",
                  "https://brunch.co.kr/@other/1"):
            self.assertFalse(same_blog(REGISTERED, u), u)

    def test_unreadable_registered_value_blocks(self):
        """맨 핸들로 저장된 유저(woorim 등)는 통과시키지 않는다 — 기존 동작 유지."""
        for reg in ("woorim-happy", "", None, "muk_soul"):
            self.assertFalse(same_blog(reg, "https://blog.naver.com/woorim-happy/1"), repr(reg))

    def test_empty_author_never_matches(self):
        """빈 값끼리 같다고 보면 아무 주소나 통과한다."""
        self.assertFalse(same_blog("https://m.blog.naver.com", "https://m.blog.naver.com"))


class TestJunkInput(unittest.TestCase):
    def test_never_raises(self):
        for bad in (None, "", "   ", 123, [], {}, "그냥 텍스트", "://", "https://"):
            r = parse_blog_ref(bad)
            self.assertIsInstance(r.platform, str, repr(bad))
            self.assertFalse(r.is_post, repr(bad))


if __name__ == "__main__":
    unittest.main()
