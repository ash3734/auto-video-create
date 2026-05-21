"""티스토리 블로그 크롤러.

cycle-2 신규. 일반적인 *.tistory.com 글에서 본문 / 이미지 / 영상 URL 을 추출한다.

티스토리는 사용자 스킨이 매우 다양해 모든 케이스 커버는 어려움. 1차 사이클은 가장 흔한
패턴(article.entry-content / .article / #content / .tt_article_useless_p_margin) 위주로
보수적으로 추출하고, 실패하면 빈 결과 + 예외로 명확히 알린다.
"""
import json
from typing import List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# 흔히 사용되는 본문 컨테이너 선택자 (순서대로 시도)
ARTICLE_SELECTORS = [
    "article",
    ".entry-content",
    "#content .article",
    ".article",
    "#content",
    ".tt_article_useless_p_margin",
    ".contents_style",
]

# 본문에서 제외할 영역
EXCLUDE_SELECTORS = [
    ".another_category",
    ".container_postbtn",
    ".related_posts",
    ".search_post",
    ".tt-comment",
    "#comment",
    ".comment",
]


def _is_likely_content_image(url: str) -> bool:
    """광고/아이콘성 이미지는 제외하기 위한 간단한 휴리스틱."""
    lower = url.lower()
    if any(kw in lower for kw in ["icon", "logo", "btn_", "blank.gif", "spacer", "tracking"]):
        return False
    if lower.endswith(".svg"):
        return False
    return lower.startswith(("http://", "https://"))


def _collect_image_candidates(img_tag) -> List[str]:
    """img 태그의 src / data-src / srcset 등에서 URL 후보를 수집."""
    candidates: List[str] = []
    for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-url"):
        v = img_tag.get(attr)
        if v:
            candidates.append(v)
    srcset = img_tag.get("srcset")
    if srcset:
        for item in srcset.split(","):
            piece = item.strip().split(" ")[0]
            if piece:
                candidates.append(piece)
    return candidates


def extract_blog_content(url: str) -> Tuple[str, List[str], List[str]]:
    """티스토리 글에서 본문 텍스트, 이미지 URL 리스트, 비디오 URL 리스트 추출."""
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 본문 컨테이너 찾기
    container = None
    for selector in ARTICLE_SELECTORS:
        node = soup.select_one(selector)
        if node:
            container = node
            break
    if container is None:
        container = soup.body or soup

    # 제외 영역 제거
    for exc_selector in EXCLUDE_SELECTORS:
        for node in container.select(exc_selector):
            node.decompose()

    # 텍스트
    text = container.get_text(separator="\n", strip=True)

    # 이미지
    image_set = []
    seen = set()
    for img in container.find_all("img"):
        for candidate in _collect_image_candidates(img):
            full_url = urljoin(url, candidate.strip())
            if not _is_likely_content_image(full_url):
                continue
            if full_url in seen:
                continue
            seen.add(full_url)
            image_set.append(full_url)

    # 비디오 (티스토리는 video 또는 iframe 으로 다양함. iframe 은 1차 사이클에서 미지원)
    videos = []
    for v in container.find_all("video"):
        src = v.get("src")
        if src:
            videos.append(urljoin(url, src))

    return text, image_set, videos
