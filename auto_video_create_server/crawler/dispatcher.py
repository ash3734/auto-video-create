"""크롤러 dispatcher — URL 도메인 기반 분기.

cycle-2 신규. ADR-1 (architecture.md) 참조.

지원 플랫폼:
- blog.naver.com           → crawler.naver
- *.tistory.com            → crawler.tistory
- brunch.co.kr             → crawler.brunch

비지원 플랫폼은 UnsupportedPlatformError 를 raise.
"""
from typing import List, Tuple
from urllib.parse import urlparse

from . import naver, tistory, brunch


class UnsupportedPlatformError(Exception):
    """지원하지 않는 블로그 플랫폼."""


def extract(url: str) -> Tuple[str, List[str], List[str], str]:
    """블로그 URL 에서 본문/이미지/영상/플랫폼명을 추출.

    Returns: (text, images, videos, platform)
    Raises: UnsupportedPlatformError — 지원 안 되는 도메인일 때
    """
    host = urlparse(url).netloc.lower()

    if "blog.naver.com" in host or host == "m.blog.naver.com":
        text, images, videos = naver.extract_blog_content(url)
        return text, images, videos, "naver"

    if host.endswith(".tistory.com"):
        text, images, videos = tistory.extract_blog_content(url)
        return text, images, videos, "tistory"

    if "brunch.co.kr" in host:
        text, images, videos = brunch.extract_blog_content(url)
        return text, images, videos, "brunch"

    raise UnsupportedPlatformError(host)
