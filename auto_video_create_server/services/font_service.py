"""
font_service.py — cycle-3 신규

한글 지원 폰트 목록을 Google Fonts API에서 가져와 캐싱한다.

- GOOGLE_FONTS_API_KEY 환경변수 필요.
- Lambda 인스턴스 레벨 메모리 캐시 (lru_cache).
  cold start 이후 첫 호출에만 Google API 실호출. 이후 동일 인스턴스는 캐시 반환.
- API Key 없거나 호출 실패 시 FALLBACK_FONTS 반환 (graceful fallback).
"""

import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────
GOOGLE_FONTS_API_URL = (
    "https://www.googleapis.com/webfonts/v1/webfonts"
    "?subset=korean&sort=alpha"
)

# Google Fonts API 장애 / Key 미설정 시 fallback 정적 목록
# data-model.md §6 FONT_FAMILY_ALLOWED_FALLBACK 기준
FALLBACK_FONTS: list[dict] = [
    {"family": "Black Han Sans",  "category": "display",     "slug": "black-han-sans"},
    {"family": "Cute Font",       "category": "display",     "slug": "cute-font"},
    {"family": "Do Hyeon",        "category": "sans-serif",  "slug": "do-hyeon"},
    {"family": "Dokdo",           "category": "display",     "slug": "dokdo"},
    {"family": "East Sea Dokdo",  "category": "handwriting", "slug": "east-sea-dokdo"},
    {"family": "Gamja Flower",    "category": "display",     "slug": "gamja-flower"},
    {"family": "Gothic A1",       "category": "sans-serif",  "slug": "gothic-a1"},
    {"family": "Gowun Batang",    "category": "serif",       "slug": "gowun-batang"},
    {"family": "Gowun Dodum",     "category": "sans-serif",  "slug": "gowun-dodum"},
    {"family": "Hi Melody",       "category": "handwriting", "slug": "hi-melody"},
    {"family": "IBM Plex Sans KR","category": "sans-serif",  "slug": "ibm-plex-sans-kr"},
    {"family": "Jua",             "category": "sans-serif",  "slug": "jua"},
    {"family": "Kirang Haerang",  "category": "display",     "slug": "kirang-haerang"},
    {"family": "Nanum Gothic",    "category": "sans-serif",  "slug": "nanum-gothic"},
    {"family": "Nanum Gothic Coding", "category": "monospace", "slug": "nanum-gothic-coding"},
    {"family": "Nanum Myeongjo",  "category": "serif",       "slug": "nanum-myeongjo"},
    {"family": "Nanum Pen Script","category": "handwriting", "slug": "nanum-pen-script"},
    {"family": "Noto Sans KR",    "category": "sans-serif",  "slug": "noto-sans-kr"},
    {"family": "Noto Serif KR",   "category": "serif",       "slug": "noto-serif-kr"},
    {"family": "Orbit",           "category": "sans-serif",  "slug": "orbit"},
    {"family": "Poor Story",      "category": "display",     "slug": "poor-story"},
    {"family": "Prompt",          "category": "sans-serif",  "slug": "prompt"},
    {"family": "Single Day",      "category": "display",     "slug": "single-day"},
    {"family": "Song Myung",      "category": "serif",       "slug": "song-myung"},
    {"family": "Stylish",         "category": "sans-serif",  "slug": "stylish"},
    {"family": "Sunflower",       "category": "sans-serif",  "slug": "sunflower"},
    {"family": "Tmon Mon Round New Basic", "category": "sans-serif", "slug": "tmon-mon-round-new-basic"},
    {"family": "Yeon Sung",       "category": "display",     "slug": "yeon-sung"},
]


def _build_slug(family: str) -> str:
    """Google Fonts family 이름 → Creatomate CDN 썸네일 slug 변환."""
    return family.lower().replace(" ", "-")


@lru_cache(maxsize=1)
def _fetch_korean_fonts_cached() -> tuple[dict, ...]:
    """
    Google Fonts API를 호출하여 Korean subset 폰트 목록을 반환한다.
    lru_cache 로 Lambda 인스턴스 수명 동안 캐시 유지.

    반환 타입이 tuple인 이유: list는 hashable 하지 않아 lru_cache 불가.
    호출 측에서 list로 변환하여 사용.
    """
    api_key = os.environ.get("GOOGLE_FONTS_API_KEY", "")
    if not api_key:
        logger.warning("[font_service] GOOGLE_FONTS_API_KEY 미설정 — fallback 반환")
        return tuple(FALLBACK_FONTS)

    try:
        import httpx  # Lambda 레이어 또는 requirements.txt 에 포함
        url = f"{GOOGLE_FONTS_API_URL}&key={api_key}"
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        fonts = [
            {
                "family": item["family"],
                "category": item.get("category", "sans-serif"),
                "slug": _build_slug(item["family"]),
            }
            for item in items
        ]
        logger.info(f"[font_service] Google Fonts Korean subset 로드 완료: {len(fonts)}개")
        return tuple(fonts)
    except ImportError:
        # httpx 미설치 환경 — requests 로 fallback
        logger.warning("[font_service] httpx 미설치 — requests 로 재시도")
        return _fetch_with_requests(api_key)
    except Exception as e:
        logger.error(f"[font_service] Google Fonts API 호출 실패: {e} — fallback 반환")
        return tuple(FALLBACK_FONTS)


def _fetch_with_requests(api_key: str) -> tuple[dict, ...]:
    """httpx 없는 환경 대비 requests 사용 fallback."""
    try:
        import requests as req_lib
        url = f"{GOOGLE_FONTS_API_URL}&key={api_key}"
        resp = req_lib.get(url, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        fonts = [
            {
                "family": item["family"],
                "category": item.get("category", "sans-serif"),
                "slug": _build_slug(item["family"]),
            }
            for item in items
        ]
        logger.info(f"[font_service] Google Fonts Korean subset 로드 완료(requests): {len(fonts)}개")
        return tuple(fonts)
    except Exception as e:
        logger.error(f"[font_service] requests fallback 실패: {e} — 정적 fallback 반환")
        return tuple(FALLBACK_FONTS)


def get_korean_fonts() -> list[dict]:
    """
    한글 지원 폰트 목록 반환. 캐시 히트 시 Google API 재호출 없음.
    항상 list[dict] 반환 (캐시 내부는 tuple이지만 외부 인터페이스는 list).
    """
    return list(_fetch_korean_fonts_cached())


def get_allowed_font_families() -> set[str]:
    """
    PUT /api/blog/subtitle-settings 에서 font_family 유효성 검증에 사용.
    캐시된 폰트 목록에서 family 이름 set을 반환.
    """
    return {f["family"] for f in get_korean_fonts()}
