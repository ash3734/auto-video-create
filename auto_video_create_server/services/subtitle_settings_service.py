"""
subtitle_settings_service.py — cycle-3 신규, feat/style-templates 확장

사용자별 자막 스타일 설정을 S3 users.json 에서 읽고 쓴다.

data-model.md §1~§3 스키마 준수.
기존 deduct_credits / account_service 패턴(S3 read-modify-write)과 동일 방식.

feat/style-templates: 계정당 단일 subtitle_settings 를 이름 붙인 템플릿 최대 5개
(subtitle_templates)로 확장. 레거시 단일 subtitle_settings 만 있는 계정은 읽을 때
자동 마이그레이션(첫 조회 시 변환, 다음 저장 시점에 영속화 — lazy).
"""

import json
import logging
import re
import uuid
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

# feat/style-templates: 계정당 최대 저장 가능한 이름 붙인 템플릿 개수
MAX_SUBTITLE_TEMPLATES = 5

_s3 = boto3.client("s3", region_name="ap-northeast-2")


# ─────────────────────────────────────────────
# feat/style-templates 전용 예외
# ─────────────────────────────────────────────

class TemplateLimitReachedError(Exception):
    """계정당 템플릿 개수(MAX_SUBTITLE_TEMPLATES)를 초과해 생성 시도할 때 발생."""


class TemplateNotFoundError(Exception):
    """지정한 template_id 가 사용자의 템플릿 목록에 없을 때 발생."""


class LastTemplateError(Exception):
    """마지막 남은 1개 템플릿을 삭제하려 할 때 발생 (최소 1개 유지)."""


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


def validate_text_style(style: dict, allowed_families: set[str]) -> list[str]:
    """
    단일 TextStyle(title 또는 subtitle 섹션 하나) 검증 공개 wrapper.
    feat/style-templates PUT(부분 수정) 처럼 섹션 하나만 검증해야 할 때 사용.
    반환: 오류 메시지 목록 (빈 목록 = 통과).
    """
    return _validate_text_style(style, allowed_families)


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
# feat/style-templates — 이름 붙인 템플릿 CRUD (최대 MAX_SUBTITLE_TEMPLATES 개)
# ─────────────────────────────────────────────

# 마이그레이션된 legacy 템플릿의 id 를 만들 때 쓰는 고정 네임스페이스.
# uuid.uuid5 는 (namespace, name) 이 같으면 항상 동일한 UUID 를 반환한다 — 이 성질을
# 이용해, 아직 영속화되지 않은(=lazy) 상태에서 GET 을 여러 번 호출해도 같은 id 가
# 나오도록 보장한다. 만약 매번 uuid4() 로 랜덤 생성하면 "GET 으로 id 확인 → 그 id 로
# DELETE/PUT" 같은 정상 흐름이 두 번째 요청에서 404 로 깨진다(실제로 테스트에서 발견).
_LEGACY_TEMPLATE_ID_NAMESPACE = uuid.UUID("6a3f6c1e-6b8b-4b8b-9b0a-3a5b6c7d8e9f")


def _migrate_legacy_templates(user: dict) -> list[dict]:
    """
    user dict 로부터 subtitle_templates 리스트를 얻는다.

    - user["subtitle_templates"] 가 이미 있으면 그대로 반환(정상 경로).
    - 없고 legacy user["subtitle_settings"](단일 dict) 만 있으면
      [{id, name:"템플릿 1", title, subtitle}] 로 변환해 반환(마이그레이션).
      이 반환값은 in-memory 변환일 뿐 여기서 S3 에 저장하지 않는다(lazy 영속화 —
      다음 CRUD 저장 시점에 실제 write 가 일어남). id 는 user_id 기반 결정적(uuid5)
      값이라, 영속화 전에 GET 을 여러 번 호출해도 항상 같은 id 가 나온다.
    - 둘 다 없으면 빈 리스트.
    """
    templates = user.get("subtitle_templates")
    if templates is not None:
        return templates

    legacy = user.get("subtitle_settings")
    if isinstance(legacy, dict) and isinstance(legacy.get("title"), dict) and isinstance(legacy.get("subtitle"), dict):
        user_id = user.get("id", "")
        deterministic_id = str(uuid.uuid5(_LEGACY_TEMPLATE_ID_NAMESPACE, f"legacy-subtitle-settings-{user_id}"))
        return [
            {
                "id": deterministic_id,
                "name": "템플릿 1",
                "title": legacy["title"],
                "subtitle": legacy["subtitle"],
            }
        ]

    return []


def get_subtitle_templates(user_id: str) -> list[dict]:
    """
    users.json 에서 user_id 에 해당하는 subtitle_templates 목록 반환.
    레거시 단일 subtitle_settings 만 있으면 마이그레이션된 값을 반환(영속화 안 함).
    사용자 없으면 빈 리스트.
    """
    try:
        users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
        for user in users:
            if user["id"] == user_id:
                templates = _migrate_legacy_templates(user)
                logger.info(
                    f"[subtitle_templates] GET user={user_id} count={len(templates)}"
                )
                return templates
        logger.warning(f"[subtitle_templates] GET user={user_id} — 사용자 없음")
        return []
    except Exception as e:
        logger.error(f"[subtitle_templates] GET 실패 user={user_id}: {e}")
        raise


def create_subtitle_template(user_id: str, name: str, title: dict, subtitle: dict) -> dict:
    """
    신규 이름 붙인 템플릿 생성.

    - 사용자 없으면 LookupError.
    - 기존 템플릿(마이그레이션 포함)이 이미 MAX_SUBTITLE_TEMPLATES 개면 TemplateLimitReachedError.
    - 성공 시 생성된 템플릿 dict({id, name, title, subtitle}) 반환.
    - S3 read-modify-write 패턴 (기존 save_subtitle_settings 와 동일 방식).
    """
    try:
        users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
        target_user = None
        for user in users:
            if user["id"] == user_id:
                target_user = user
                break

        if target_user is None:
            logger.warning(f"[subtitle_templates] CREATE user={user_id} — 사용자 없음")
            raise LookupError(f"사용자를 찾을 수 없습니다: {user_id}")

        templates = _migrate_legacy_templates(target_user)
        if len(templates) >= MAX_SUBTITLE_TEMPLATES:
            raise TemplateLimitReachedError(
                f"템플릿은 최대 {MAX_SUBTITLE_TEMPLATES}개까지 저장할 수 있습니다."
            )

        new_template = {
            "id": str(uuid.uuid4()),
            "name": name,
            "title": title,
            "subtitle": subtitle,
        }
        target_user["subtitle_templates"] = templates + [new_template]

        _s3.put_object(
            Bucket=BUCKET_USERS,
            Key=KEY_USERS,
            Body=json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        logger.info(f"[subtitle_templates] CREATE user={user_id} template_id={new_template['id']} 완료")
        return new_template
    except (LookupError, TemplateLimitReachedError):
        raise
    except Exception as e:
        logger.error(f"[subtitle_templates] CREATE 실패 user={user_id}: {e}")
        raise


def update_subtitle_template(
    user_id: str,
    template_id: str,
    name: Optional[str] = None,
    title: Optional[dict] = None,
    subtitle: Optional[dict] = None,
) -> dict:
    """
    기존 템플릿 부분 수정 (name/title/subtitle 중 전달된(None 이 아닌) 값만 반영).

    - 사용자 없으면 LookupError.
    - template_id 가 목록에 없으면 TemplateNotFoundError.
    - 성공 시 수정된 템플릿 dict 반환.
    """
    try:
        users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
        target_user = None
        for user in users:
            if user["id"] == user_id:
                target_user = user
                break

        if target_user is None:
            logger.warning(f"[subtitle_templates] UPDATE user={user_id} — 사용자 없음")
            raise LookupError(f"사용자를 찾을 수 없습니다: {user_id}")

        templates = _migrate_legacy_templates(target_user)
        updated_template = None
        new_templates = []
        for tpl in templates:
            if tpl.get("id") == template_id:
                if name is not None:
                    tpl = {**tpl, "name": name}
                if title is not None:
                    tpl = {**tpl, "title": title}
                if subtitle is not None:
                    tpl = {**tpl, "subtitle": subtitle}
                updated_template = tpl
            new_templates.append(tpl)

        if updated_template is None:
            logger.warning(f"[subtitle_templates] UPDATE user={user_id} template_id={template_id} — 템플릿 없음")
            raise TemplateNotFoundError(f"템플릿을 찾을 수 없습니다: {template_id}")

        target_user["subtitle_templates"] = new_templates

        _s3.put_object(
            Bucket=BUCKET_USERS,
            Key=KEY_USERS,
            Body=json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        logger.info(f"[subtitle_templates] UPDATE user={user_id} template_id={template_id} 완료")
        return updated_template
    except (LookupError, TemplateNotFoundError):
        raise
    except Exception as e:
        logger.error(f"[subtitle_templates] UPDATE 실패 user={user_id} template_id={template_id}: {e}")
        raise


def delete_subtitle_template(user_id: str, template_id: str) -> None:
    """
    템플릿 삭제.

    - 사용자 없으면 LookupError.
    - template_id 가 목록에 없으면 TemplateNotFoundError.
    """
    try:
        users = load_json_from_s3(BUCKET_USERS, KEY_USERS)
        target_user = None
        for user in users:
            if user["id"] == user_id:
                target_user = user
                break

        if target_user is None:
            logger.warning(f"[subtitle_templates] DELETE user={user_id} — 사용자 없음")
            raise LookupError(f"사용자를 찾을 수 없습니다: {user_id}")

        templates = _migrate_legacy_templates(target_user)
        new_templates = [tpl for tpl in templates if tpl.get("id") != template_id]

        if len(new_templates) == len(templates):
            logger.warning(f"[subtitle_templates] DELETE user={user_id} template_id={template_id} — 템플릿 없음")
            raise TemplateNotFoundError(f"템플릿을 찾을 수 없습니다: {template_id}")

        # 최소 1개 템플릿 유지 — 마지막 남은 템플릿 삭제 방지 (서버측 강제).
        # FE 도 버튼을 비활성화하지만, 동시 요청/다른 클라이언트 경로에서 0개가 되는 것을 막는다.
        if len(new_templates) == 0:
            logger.warning(f"[subtitle_templates] DELETE user={user_id} template_id={template_id} — 마지막 템플릿 삭제 거부")
            raise LastTemplateError("마지막 템플릿은 삭제할 수 없습니다.")

        target_user["subtitle_templates"] = new_templates

        _s3.put_object(
            Bucket=BUCKET_USERS,
            Key=KEY_USERS,
            Body=json.dumps(users, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        logger.info(f"[subtitle_templates] DELETE user={user_id} template_id={template_id} 완료")
    except (LookupError, TemplateNotFoundError, LastTemplateError):
        raise
    except Exception as e:
        logger.error(f"[subtitle_templates] DELETE 실패 user={user_id} template_id={template_id}: {e}")
        raise


# ─────────────────────────────────────────────
# Creatomate modifications 주입 헬퍼
# ─────────────────────────────────────────────

def apply_subtitle_settings_to_variables(
    variables: dict,
    subtitle_settings: Optional[dict],
    subtitle_suffixes: Optional[list] = None,
) -> None:
    """
    subtitle_settings 를 Creatomate modifications dict (variables) 에 주입.
    subtitle_settings 가 None/비어있으면 아무것도 주입 안 함 (기존 동작 유지).

    subtitle_suffixes: 장면 수별 자막 element suffix 목록 (scene_counts 에서 룩업).
        None 이면 기본(5장면) suffix 사용 — 기존 동작 유지.
        빈 목록이면 자막 주입을 건너뛴다 (템플릿 suffix 미확보 상태).

    api-contract.md "BE 처리 로직 — Creatomate modifications 주입" 구현.
    변수는 in-place 수정.
    """
    if not subtitle_settings:
        return
    suffixes = SUBTITLE_SUFFIXES if subtitle_suffixes is None else subtitle_suffixes

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

    for suffix in suffixes:
        variables[f"Subtitles-{suffix}.font_family"] = sub_font
        variables[f"Subtitles-{suffix}.font_size"] = sub_size
        variables[f"Subtitles-{suffix}.fill_color"] = sub_color
        variables[f"Subtitles-{suffix}.transcript_color"] = sub_color
