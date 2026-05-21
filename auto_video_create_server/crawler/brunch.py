"""브런치 블로그 크롤러.

cycle-2 신규. brunch.co.kr 글에서 본문 / 이미지 / 영상 URL 을 추출한다.
브런치는 구조가 비교적 안정적이라 .wrap_body 또는 .post_content 위주로 추출.
"""
from typing import List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


ARTICLE_SELECTORS = [
    "div.wrap_body",
    ".post_content",
    "article",
    "#wrap_body",
]


def _collect_image_candidates(img_tag) -> List[str]:
    candidates: List[str] = []
    for attr in ("src", "data-src", "data-original"):
        v = img_tag.get(attr)
        if v:
            candidates.append(v)
    return candidates


def _normalize_brunch_image(url: str) -> str:
    """브런치 이미지는 사이즈 파라미터가 붙는 경우가 많음. 원본 사이즈 우선 사용."""
    return url.split("?")[0]


def extract_blog_content(url: str) -> Tuple[str, List[str], List[str]]:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    container = None
    for selector in ARTICLE_SELECTORS:
        node = soup.select_one(selector)
        if node:
            container = node
            break
    if container is None:
        container = soup.body or soup

    # 댓글 / 관련 글 제외
    for selector in (".article_comment", ".related_article", ".author_zone"):
        for node in container.select(selector):
            node.decompose()

    text = container.get_text(separator="\n", strip=True)

    images: List[str] = []
    seen = set()
    for img in container.find_all("img"):
        for candidate in _collect_image_candidates(img):
            full_url = urljoin(url, candidate.strip())
            full_url = _normalize_brunch_image(full_url)
            if not full_url.startswith(("http://", "https://")):
                continue
            if full_url in seen:
                continue
            seen.add(full_url)
            images.append(full_url)

    videos: List[str] = []
    for v in container.find_all("video"):
        src = v.get("src")
        if src:
            videos.append(urljoin(url, src))

    return text, images, videos
