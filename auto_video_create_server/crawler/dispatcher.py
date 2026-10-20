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


def extract_rich(url: str) -> Tuple[str, List[str], List[str], str, List[dict], List[dict]]:
    """블로그 URL 에서 본문/이미지/영상/플랫폼명 + 이미지별 컨텍스트를 추출.

    VOC-2 (이미지 자동 매칭) 신규.
    - naver: 캡션/주변 텍스트 완전 지원
    - tistory/brunch: v1 은 순서 정보만 (캡션 빈 문자열)

    Returns: (text, images, videos, platform, image_infos, video_infos)
             image_infos = [{"url", "caption", "context"}, ...] — images 와 같은 순서
             video_infos = 같은 형태 — videos 와 같은 순서 (2026-10-20, 영상 자동 추천)
    Raises: UnsupportedPlatformError — 지원 안 되는 도메인일 때
    """
    host = urlparse(url).netloc.lower()

    if "blog.naver.com" in host or host == "m.blog.naver.com":
        text, images, videos, image_infos, video_infos = naver.extract_blog_content_rich(url)
        return text, images, videos, "naver", image_infos, video_infos

    if host.endswith(".tistory.com"):
        text, images, videos = tistory.extract_blog_content(url)
    elif "brunch.co.kr" in host:
        text, images, videos = brunch.extract_blog_content(url)
    else:
        raise UnsupportedPlatformError(host)

    platform = "tistory" if host.endswith(".tistory.com") else "brunch"
    image_infos = [{"url": u, "caption": "", "context": ""} for u in images]
    video_infos = [{"url": u, "caption": "", "context": ""} for u in videos]
    return text, images, videos, platform, image_infos, video_infos


def extract(url: str) -> Tuple[str, List[str], List[str], str]:
    """블로그 URL 에서 본문/이미지/영상/플랫폼명을 추출. (하위호환 시그니처)

    Returns: (text, images, videos, platform)
    Raises: UnsupportedPlatformError — 지원 안 되는 도메인일 때
    """
    text, images, videos, platform, _, _ = extract_rich(url)
    return text, images, videos, platform
