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

2026-10-20 (영상도 추천):
- 크롤러가 네이버 본문 영상을 처음으로 가져온다 (crawler/naver_video.py). 그 전엔 영상이
  0개라 추천될 수가 없었다.
- AI 에게 주는 목록 = 사진(최대 PROMPT_IMAGE_LIMIT) + 영상. 번호는 이어서 매긴다.
- 영상 우선: 장면의 절반까지는 영상 (video_target). AI 가 덜 골랐으면 본문에서 가까운 사진
  칸을 영상으로 바꾼다 (_build_suggested_sections).
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


PROMPT_IMAGE_LIMIT = 20


def video_target(scene_count: int, video_count: int) -> int:
    """영상으로 채울 장면 수 — 장면의 절반(올림)까지, 영상이 그보다 적으면 영상 수만큼.

    PO (2026-10-20): "영상이 영상미가 더 좋으니 사진보다 우선순위를 높여 달라".
    전부 영상으로 채우지 않는 건, 블로그 영상은 같은 장면을 길게 찍은 게 많아서다.
    """
    return min(video_count, (scene_count + 1) // 2)


def _build_suggested_sections(indices, images, videos=(), offered_images=None, positions=None):
    """0-based 인덱스 리스트 → suggested_sections 조립.

    indices 는 AI 에게 보여준 목록(사진 앞 offered_images 개 + 영상 전부) 기준 번호다.
    offered_images 를 안 주면 사진 전부를 보여준 것으로 본다 (영상이 없던 시절과 같다).
    positions: {url: 본문 순서} — 영상과 글에서 가장 가까운 사진을 찾을 때 쓴다.

    1) AI 가 고른 대로.
    2) 영상 우선 (video_target): AI 가 영상을 덜 골랐으면 남은 영상을 넣는다. 빈 칸(AI 가 못 고른
       칸)이 먼저고, 없으면 **본문에서 그 영상과 가장 가까이 있던 사진**의 칸을 영상으로 바꾼다 —
       같은 대목을 찍은 사진일 가능성이 높다. 본문 순서를 모르면 마지막 사진 칸.
    3) 그래도 빈 칸은 위치 기반 폴백: 안 쓰인 사진을 본문 순서대로, 그다음 영상.
    4) 그래도 모자라면 {"type": "default", "url": None} (기존 AI 배경 슬롯 규칙).
    """
    videos = list(videos)
    positions = positions or {}
    k = len(images) if offered_images is None else offered_images
    offered = [("image", u) for u in images[:k]] + [("video", u) for u in videos]
    picked = [offered[i] if i is not None and 0 <= i < len(offered) else None for i in indices]

    need = video_target(len(picked), len(videos)) - sum(1 for m in picked if m and m[0] == "video")
    spare = [("video", u) for u in videos if ("video", u) not in picked]
    while need > 0 and spare:
        video = spare.pop(0)
        free = [i for i, m in enumerate(picked) if m is None]
        photo_slots = [i for i, m in enumerate(picked) if m and m[0] == "image"]
        if free:
            slot = free[-1]
        elif photo_slots:
            vpos = positions.get(video[1])
            known = [i for i in photo_slots if positions.get(picked[i][1]) is not None]
            if vpos is not None and known:
                slot = min(known, key=lambda i: abs(positions[picked[i][1]] - vpos))
            else:
                slot = photo_slots[-1]
        else:
            break
        picked[slot] = video
        need -= 1

    used = {m for m in picked if m}
    remaining = [m for m in [("image", u) for u in images] + [("video", u) for u in videos]
                 if m not in used]
    sections = []
    for m in picked:
        if m is None and remaining:
            m = remaining.pop(0)
        if m is not None:
            sections.append({"type": m[0], "url": m[1]})
        else:
            sections.append({"type": "default", "url": None})
    return sections


def get_blog_media_and_scripts(blog_url: str, scene_count: int = 5) -> dict:
    """블로그 URL 1개 → 추출 + 분류 + 스크립트 생성 + 슬롯 부족 카운트 + 자동 배정 제안.

    scene_count: 유저가 고른 장면 수(4~8). 스크립트/슬롯 개수가 이 값을 따른다.
    """
    scene_count = normalize_scene_count(scene_count)
    text, images, videos, platform, image_infos, video_infos = dispatcher_extract_rich(blog_url)
    category = classify_blog(text)
    shown_images = (image_infos or [])[:PROMPT_IMAGE_LIMIT]
    media_infos = shown_images + [dict(v, kind="video") for v in (video_infos or [])]
    title, scripts, seo = summarize_for_shorts_sets(
        text, category=category, image_infos=media_infos or None, scene_count=scene_count
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
        # 배포용 문구 — 없거나 실패해도 빈 값이라 FE 가 블록을 숨기고 넘어간다.
        "seo": seo,
    }
    # VOC-2: 자동 배정 제안. 실패해도 전체 응답은 정상 (필드 생략 → FE 가 기존 폴백).
    try:
        indices = _normalize_image_indices(scripts, len(media_infos))
        positions = {i["url"]: i.get("pos") for i in (image_infos or []) + (video_infos or [])
                     if i.get("pos") is not None}
        result["suggested_sections"] = _build_suggested_sections(
            indices, images, videos, offered_images=len(shown_images), positions=positions)
    except Exception as e:
        print(f"[blog_shorts] suggested_sections 조립 실패 — 필드 생략: {e}")
    return result
