"""블로그 → 미디어/스크립트 추출 오케스트레이터.

cycle-2 갱신:
- crawler.dispatcher 로 멀티 플랫폼 분기 (네이버 / 티스토리 / 브런치)
- services.classifier 로 맛집 vs 일반 자동 분류
- summarize 에 category 전달 → 카테고리별 프롬프트 분기
- default_slot_count 계산 (이미지 + 영상 < 5 일 때)
"""
from crawler.dispatcher import extract as dispatcher_extract
from crawler.dispatcher import UnsupportedPlatformError  # noqa: F401  (re-export)
from crawler.naver import extract_blog_content  # noqa: F401  (backward-compat re-export)
from .summarize import summarize_for_shorts_sets
from .classifier import classify_blog


def get_blog_media_and_scripts(blog_url: str) -> dict:
    """블로그 URL 1개 → 추출 + 분류 + 스크립트 생성 + 슬롯 부족 카운트."""
    text, images, videos, platform = dispatcher_extract(blog_url)
    category = classify_blog(text)
    title, scripts = summarize_for_shorts_sets(text, category=category)
    # 5개 슬롯 중 이미지+영상으로 채워지지 않는 슬롯 수
    default_slot_count = max(0, 5 - (len(images) + len(videos)))
    return {
        "text": text,
        "images": images,
        "videos": videos,
        "title": title,
        "scripts": scripts,
        "category": category,
        "platform": platform,
        "default_slot_count": default_slot_count,
    }
