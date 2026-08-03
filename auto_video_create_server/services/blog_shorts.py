"""블로그 → 미디어/스크립트 추출 오케스트레이터.

cycle-2 갱신:
- crawler.dispatcher 로 멀티 플랫폼 분기 (네이버 / 티스토리 / 브런치)
- services.classifier 로 맛집 vs 일반 자동 분류
- summarize 에 category 전달 → 카테고리별 프롬프트 분기
- default_slot_count 계산 (이미지 + 영상 < 5 일 때)

VOC-2 갱신 (이미지 자동 매칭):
- dispatcher.extract_rich 로 이미지별 캡션/주변 텍스트 수집 (naver 완전 지원)
- summarize 피기백으로 스크립트별 image_index(1-based) 수신
- suggested_sections 조립: LLM 매칭 → 위치 기반 폴백 → 부족分 default
  (자동 배정은 FE 의 default 제안일 뿐 — 유저가 수동으로 바꿀 수 있다)
"""
from crawler.dispatcher import extract_rich as dispatcher_extract_rich
from crawler.dispatcher import UnsupportedPlatformError  # noqa: F401  (re-export)
from crawler.naver import extract_blog_content  # noqa: F401  (backward-compat re-export)
from .summarize import summarize_for_shorts_sets
from .classifier import classify_blog
from .scene_counts import normalize_scene_count


def _normalize_image_indices(scripts, image_count):
    """scripts 원소에서 image_index(1-based)를 꺼내 0-based 유효 인덱스 리스트로.

    - scripts 원소 dict 에서 image_index 를 제거한다 (FE 응답 스키마 오염 방지).
    - 무효(범위 밖/비정수/bool)·중복(첫 등장 우선) 인덱스는 None 처리.
    """
    used = set()
    indices = []
    for s in scripts:
        idx = None
        if isinstance(s, dict):
            raw = s.pop("image_index", None)
            if isinstance(raw, int) and not isinstance(raw, bool):
                zero = raw - 1
                if 0 <= zero < image_count and zero not in used:
                    idx = zero
                    used.add(zero)
        indices.append(idx)
    return indices


def _build_suggested_sections(indices, images):
    """0-based 인덱스 리스트 → suggested_sections 조립.

    - None 슬롯은 위치 기반 폴백: 아직 안 쓰인 이미지를 본문 등장 순서대로 배정.
    - 이미지가 부족하면 {"type": "default", "url": None} (기존 AI 배경 슬롯 규칙).
    """
    used = {i for i in indices if i is not None}
    remaining = [i for i in range(len(images)) if i not in used]
    sections = []
    for idx in indices:
        if idx is None and remaining:
            idx = remaining.pop(0)
        if idx is not None:
            sections.append({"type": "image", "url": images[idx]})
        else:
            sections.append({"type": "default", "url": None})
    return sections


def get_blog_media_and_scripts(blog_url: str, scene_count: int = 5) -> dict:
    """블로그 URL 1개 → 추출 + 분류 + 스크립트 생성 + 슬롯 부족 카운트 + 자동 배정 제안.

    scene_count: 유저가 고른 장면 수(4~8). 스크립트/슬롯 개수가 이 값을 따른다.
    """
    scene_count = normalize_scene_count(scene_count)
    text, images, videos, platform, image_infos = dispatcher_extract_rich(blog_url)
    category = classify_blog(text)
    title, scripts = summarize_for_shorts_sets(
        text, category=category, image_infos=image_infos or None, scene_count=scene_count
    )
    # N개 슬롯 중 이미지+영상으로 채워지지 않는 슬롯 수
    default_slot_count = max(0, scene_count - (len(images) + len(videos)))
    result = {
        "text": text,
        "images": images,
        "videos": videos,
        "title": title,
        "scripts": scripts,
        "category": category,
        "platform": platform,
        "default_slot_count": default_slot_count,
        "scene_count": scene_count,
    }
    # VOC-2: 자동 배정 제안. 실패해도 전체 응답은 정상 (필드 생략 → FE 가 기존 폴백).
    try:
        indices = _normalize_image_indices(scripts, len(images))
        result["suggested_sections"] = _build_suggested_sections(indices, images)
    except Exception as e:
        print(f"[blog_shorts] suggested_sections 조립 실패 — 필드 생략: {e}")
    return result
