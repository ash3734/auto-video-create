"""
subtitle_settings_service.py — cycle-3 신규

사용자별 자막 스타일 설정을 S3 users.json 에서 읽고 쓴다.

data-model.md §1~§3 스키마 준수.
기존 deduct_credits / account_service 패턴(S3 read-modify-write)과 동일 방식.
"""

import json
import logging
import os
import re
from typing import Optional

import boto3

from utils.s3_utils import load_json_from_s3

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 상수 (data-model.md §6)
# ─────────────────────────────────────────────
BUCKET_USERS = "blog-to-short-form-users"
KEY_USERS = "users.json"

VALID_FONT_SIZES = {"S", "M", "L"}
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# vmin 변환 테이블 (data-model.md §4)
SIZE_MAP_SUBTITLE_VMIN: dict[str, Optional[str]] = {
    "S": "4 vmin",
    "M": "6 vmin",
    "L": "8 vmin",
}
SIZE_MAP_TITLE_VMIN: dict[str, Optional[str]] = {
    "S": "6 vmin",
    "M": None,       # M → modification 미주입 = auto-fit 유지
    "L": "12 vmin",
}

# Creatomate 자막 element 식별자 (data-model.md §6 / architecture.md DEP-01)
SUBTITLE_SUFFIXES = ["6K5", "JTM", "MDV", "5Z2", "D6M"]

# 기본값 (data-model.md §3)
DEFAULT_TITLE_SETTINGS: dict = {
    "font_family": "Black Han Sans",
    "font_size": "M",
    "fill_color": "#fff100",
}
DEFAULT_SUBTITLE_SETTINGS: dict = {
    "font_family": "Noto Sans KR",
    "font_size": "M",
    "fill_color": "#ffffff",
}

_s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ap-northeast-2",
)


# ─────────────────────────────────────────────
# 유효성 검증 헬퍼
# ─────────────────────────────────────────────

def _validate_text_style(style: dict, allowed_families: set[str]) -> list[str]:
    """
    TextStyle dict 유효성 검증. 오류 메시지 목록 반환 (빈 목록 = 통과).
    font_family 검증은 allowed_families set 기준.
    """
    errors: list[str] = []

    font_family = style.get("font_family", "")
    font_size = style.get("font_size", "")
    fill_color = style.get("fill_color", "")

    if not isinstance(font_family, str) or not font_family.strip():
        errors.append("font_family 는 비어있지 않은 문자열이어야 합니다.")
    elif allowed_families and font_family not in allowed_families:
        # 허용 목록이 있을 때만 검증 (Google Fonts API 장애 시 허용 목록이 비어있을 수 있음)
        errors.append(f"허용되지 않는 font_family: {font_family!r}")

    if font_size not in VALID_FONT_SIZES:
        errors.append(f"font_size 는 S/M/L 중 하나여야 합니다. 받은 값: {font_size!r}")

    if not isinstance(fill_color, str) or not HEX_COLOR_RE.match(fill_color):
        errors.append(f"fill_color 는 #RRGGBB 형식이어야 합니다. 받은 값: {fill_color!r}")

    return errors


def validate_subtitle_settings(settings: dict, allowed_families: set[str]) -> list[str]:
    """
    subtitle_settings 전체 유효성 검증.
    반환: 오류 메시지 목록 (빈 목록 = 통과).
    """
    errors: list[str] = []
    for section in ("title", "subtitle"):
        section_data = settings.get(section)
        if not isinstance(section_data, dict):
            errors.append(f"{section} 섹션이 누락되었거나 dict 가 아닙니다.")
            continue
        section_errors = _validate_text_style(section_data, allowed_families)
        errors.extend(f"[{section}] {e}" for e in section_errors)
    return errors


# ─────────────────────────────────────────────
# S3 Read / Write
# ─────────────────────────────────────────────

def get_subtitle_settings(user_id: str) -> Optional[dict]:
    """
    users.json 에서 user_id 에 해당하는 subtitle_settings 반환.
    설정 없으면 None (FE 가 기본값으로 처리).
    """
    try:
        users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
        for user in users:
            if user["id"] == user_id:
                settings = user.get("subtitle_settings")
                logger.info(
                    f"[subtitle_settings] GET user={user_id} settings={'있음' if settings else '없음'}"
                )
                return settings
        logger.warning(f"[subtitle_settings] GET user={user_id} — 사용자 없음")
        return None
    except Exception as e:
        logger.error(f"[subtitle_settings] GET 실패 user={user_id}: {e}")
        raise


def save_subtitle_settings(user_id: str, settings: dict) -> bool:
    """
    users.json 에서 user_id 에 해당하는 subtitle_settings 를 업데이트한다.
    S3 read-modify-write 패턴 (기존 deduct_credits 와 동일).
    성공 시 True, 사용자 미발견 시 False.
    """
    try:
        users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
        user_found = False
        for user in users:
            if user["id"] == user_id:
                user["subtitle_settings"] = settings
                user_found = True
                break

        if not user_found:
            logger.warning(f"[subtitle_settings] SAVE user={user_id} — 사용자 없음")
            return False

        _s3.put_object(
            Bucket=BUCKET_USERS,
            Key=KEY_USERS,
            Body=json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        logger.info(f"[subtitle_settings] SAVE user={user_id} 완료")
        return True
    except Exception as e:
        logger.error(f"[subtitle_settings] SAVE 실패 user={user_id}: {e}")
        raise


# ─────────────────────────────────────────────
# Creatomate modifications 주입 헬퍼
# ─────────────────────────────────────────────

def apply_subtitle_settings_to_variables(
    variables: dict,
    subtitle_settings: Optional[dict],
) -> None:
    """
    subtitle_settings 를 Creatomate modifications dict (variables) 에 주입.
    subtitle_settings 가 None/비어있으면 아무것도 주입 안 함 (기존 동작 유지).

    api-contract.md "BE 처리 로직 — Creatomate modifications 주입" 구현.
    변수는 in-place 수정.
    """
    if not subtitle_settings:
        return

    ts = subtitle_settings.get("title") or {}
    ss = subtitle_settings.get("subtitle") or {}

    # 제목(title element)
    if ts.get("font_family"):
        variables["title.font_family"] = ts["font_family"]
    if ts.get("fill_color"):
        variables["title.fill_color"] = ts["fill_color"]
    title_size_vmin = SIZE_MAP_TITLE_VMIN.get(ts.get("font_size", "M"))
    if title_size_vmin:  # M 이면 None → 미주입 (auto-fit 유지)
        variables["title.font_size"] = title_size_vmin

    # 자막(Subtitles-* × 5 — 모두 동일 설정)
    sub_font = ss.get("font_family") or DEFAULT_SUBTITLE_SETTINGS["font_family"]
    sub_size = SIZE_MAP_SUBTITLE_VMIN.get(
        ss.get("font_size", "M"), "6 vmin"
    )
    sub_color = ss.get("fill_color") or DEFAULT_SUBTITLE_SETTINGS["fill_color"]

    for suffix in SUBTITLE_SUFFIXES:
        variables[f"Subtitles-{suffix}.font_family"] = sub_font
        variables[f"Subtitles-{suffix}.font_size"] = sub_size
        variables[f"Subtitles-{suffix}.fill_color"] = sub_color
