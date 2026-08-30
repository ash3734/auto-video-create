"""블로그 주소 해석 — 플랫폼/작성자/글 식별 (2026-08-30).

## 왜 생겼나

두 가지 사고가 같은 뿌리였다.

**하나.** test 알람 (2026-08-30 12:51). 유저가 `m.blog.naver.com/auctionrun0643`
(블로그 **홈**)을 넣었다. 크롤러가 본문을 못 찾아 ValueError 를 던졌고, catch-all 이
이걸 "예상치 못한 실패"로 보고 알람을 울렸다. 하지만 이건 장애가 아니라 **주소를
잘못 넣은 것**이다. 이런 알람이 쌓이면 진짜 장애를 무시하게 된다.

그렇다고 이 에러를 통째로 조용히 만들면 안 된다 — 네이버가 마크업을 바꿔 파서가
깨져도 같은 ValueError 가 나기 때문이다(코드에 그 경고가 남아 있다). **글 주소인데도
본문을 못 찾은 경우와, 애초에 글 주소가 아니었던 경우를 갈라야** 한다.

**둘.** api/blog.py 의 기존 parse_blog_url 에는 알려진 결함이 둘 있었다.

    "blog.naver.com" in host          # 부분 문자열 검사
    → blog.naver.com.attacker.io/유저아이디 가 통과한다.
      "본인 블로그만" 이라는 규칙이 무력화된다.

    path_parts[0] 만 보고 작성자를 뽑음
    → blog.naver.com/PostView.naver?blogId=X&logNo=Y (네이버가 실제로 주는 형식)
      에서 작성자를 'PostView.naver' 로 읽어 본인 글인데도 차단된다.

두 문제 다 "주소를 제대로 해석한다"는 한 가지 일이라 여기로 모은다.
"""
from __future__ import annotations

from typing import NamedTuple, Optional
from urllib.parse import parse_qs, urlparse

NAVER_HOSTS = {"blog.naver.com", "m.blog.naver.com"}
BRUNCH_HOSTS = {"brunch.co.kr", "m.brunch.co.kr"}

# 네이버가 글 목록/홈에서 쓰는 경로 조각. 작성자 아이디가 아니다.
_NAVER_NON_AUTHOR = {
    "postview.naver", "postview.nhn", "postlist.naver", "postlist.nhn",
    "prologue", "guestbook", "postsearchlist.naver",
}


class BlogRef(NamedTuple):
    """주소에서 읽어낸 것.

    platform: 'naver' | 'tistory' | 'brunch' | '' (해석 불가)
    author:   블로그 주인 식별자 (소문자). 못 읽으면 ''
    post_id:  글 식별자. 홈/목록 주소면 None
    """
    platform: str
    author: str
    post_id: Optional[str]

    @property
    def is_post(self) -> bool:
        """개별 글을 가리키는 주소인가. 홈 주소면 False."""
        return bool(self.platform) and bool(self.post_id)


def parse_blog_ref(url) -> BlogRef:
    """블로그 주소 → (플랫폼, 작성자, 글 번호). 해석 못 하면 빈 값."""
    if not isinstance(url, str) or not url.strip():
        return BlogRef("", "", None)

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return BlogRef("", "", None)

    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]
    query = parse_qs(parsed.query or "")

    def q(name):
        v = query.get(name) or []
        return v[0].strip() if v and v[0].strip() else None

    # 네이버 — 호스트는 **정확히** 일치해야 한다 (부분 문자열 금지)
    if host in NAVER_HOSTS:
        author = q("blogId") or ""
        post_id = q("logNo")
        if not author and parts and parts[0].lower() not in _NAVER_NON_AUTHOR:
            author = parts[0]
            if len(parts) >= 2 and parts[1].isdigit():
                post_id = parts[1]
        return BlogRef("naver", author.lower(), post_id)

    # 티스토리 — {author}.tistory.com/{postNo}
    if host == "tistory.com" or host.endswith(".tistory.com"):
        author = host[: -len(".tistory.com")] if host.endswith(".tistory.com") else ""
        post_id = None
        if parts:
            # /123 또는 /entry/제목 둘 다 개별 글이다
            post_id = parts[0] if parts[0].isdigit() else ("/".join(parts) if parts[0] != "category" else None)
        return BlogRef("tistory", author.lower(), post_id)

    # 브런치 — brunch.co.kr/@{author}/{no}
    if host in BRUNCH_HOSTS:
        author = ""
        post_id = None
        if parts:
            first = parts[0]
            author = first[1:] if first.startswith("@") else first
            if len(parts) >= 2:
                post_id = parts[1]
        return BlogRef("brunch", author.lower(), post_id)

    return BlogRef("", "", None)


def same_blog(registered_url, requested_url) -> bool:
    """등록된 블로그와 요청된 주소가 같은 사람의 블로그인가.

    플랫폼과 작성자가 모두 일치해야 한다. 작성자를 못 읽으면 통과시키지 않는다 —
    빈 값끼리 같다고 판단하면 아무 주소나 통과한다.
    """
    a = parse_blog_ref(registered_url)
    b = parse_blog_ref(requested_url)
    if not a.platform or not a.author:
        return False
    return a.platform == b.platform and a.author == b.author
