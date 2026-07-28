"""블로그 → 미디어/스크립트 추출 오케스트레이터.

cycle-2 갱신:
- crawler.dispatcher 로 멀티 플랫폼 분기 (네이버 / 티스토리 / 브런치)
- services.classifier 로 맛집 vs 일반 자동 분류
- summarize 에 category 전달 → 카테고리별 프롬프트 분기
- default_slot_count 계산 (이미지 + 영상 < N 일 때)

sprint-4 갱신 (B-2, architecture.md §F-4):
- concept_sample_id 파라미터 수신 → concept_samples.get_sample() 로 scene_count(N)/hook_prompt 조회
- category(classifier.py, 맛집/일반) × concept_sample(scene_count/hook_prompt) 두 축을
  동시에 summarize_for_shorts_sets() 로 전달 — 두 축은 직교(orthogonal)하며 서로 무관
- default_slot_count 계산 기준을 고정 5 → scene_count(N) 로 전환
"""
from typing import Optional

from crawler.dispatcher import extract as dispatcher_extract
from crawler.dispatcher import UnsupportedPlatformError  # noqa: F401  (re-export)
from crawler.naver import extract_blog_content  # noqa: F401  (backward-compat re-export)
from .summarize import summarize_for_shorts_sets
from .classifier import classify_blog
from .concept_samples import get_sample


def get_blog_media_and_scripts(blog_url: str, concept_sample_id: Optional[str] = None) -> dict:
    """블로그 URL 1개 → 추출 + 분류 + 스크립트 생성 + 슬롯 부족 카운트.

    concept_sample_id: 미인식/None 이면 concept_samples.get_sample() 이 sample_1(기본값)로
    폴백한다 (api-contract.md "미선택 통과 허용" 원칙).
    """
    text, images, videos, platform = dispatcher_extract(blog_url)
    category = classify_blog(text)
    sample = get_sample(concept_sample_id)
    scene_count = sample["scene_count"]
    title, scripts = summarize_for_shorts_sets(
        text,
        category=category,
        scene_count=scene_count,
        hook_prompt=sample["hook_prompt"],
    )
    # N개 슬롯 중 이미지+영상으로 채워지지 않는 슬롯 수
    default_slot_count = max(0, scene_count - (len(images) + len(videos)))
    return {
        "text": text,
        "images": images,
        "videos": videos,
        "title": title,
        "scripts": scripts,
        "category": category,
        "platform": platform,
        "default_slot_count": default_slot_count,
        "concept_sample_id": sample["concept_sample_id"],
        "scene_count": scene_count,
    }
