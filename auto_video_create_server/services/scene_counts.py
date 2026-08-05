"""장면 수(scene_count) 선택 기능 — 코드 상수 정의.

유저가 영상의 장면 수(= 스크립트 수 = 이미지 슬롯 수)를 4~8 중에서 고를 수 있다.
장면 수마다 Creatomate 템플릿이 다르므로 (composition 개수가 다름) 템플릿 ID 와
자막 element suffix 를 장면 수별로 룩업한다.

- 5: 기존 운영 템플릿 그대로 (현행 동작 유지 — 기본값)
- 4/6/7/8: PO 가 Creatomate 템플릿 제작 후 아래 상수에 채운다 (현재 placeholder=None)

템플릿 미확보 상태에서 해당 장면 수로 영상 생성을 시도하면
`scene_count_template_not_configured` 에러로 안전하게 막는다 (크래시 아님).
"""
import os
from typing import Optional

# 선택 가능한 장면 수
ALLOWED_SCENE_COUNTS = [4, 5, 6, 7, 8]
DEFAULT_SCENE_COUNT = 5

# 장면 수별 설정.
#   template_id_prod / template_id_test: Creatomate 템플릿 ID (ENV 분기)
#   subtitle_suffixes: 자막 element ID suffix — 반드시 장면 수와 같은 개수여야 한다.
#                      템플릿마다 다르므로 템플릿과 함께 확보한다.
# NOTE (2026-08-04, PO 템플릿 제공): 4/6/7/8 템플릿은 prod/test 구분 없이 동일 ID 를 사용한다
# (PO 가 장면 수당 템플릿 1개씩 제공). 5장면만 기존처럼 prod/test 가 분리돼 있다.
#
# NOTE (자막 suffix, 2026-08-04 정정): 3번 슬롯 자막은 `Subtitles-MDV` 로 **존재한다**.
# 최초 등록 시 참고한 Creatomate "API 사용" 예시(curl)에 MDV 가 빠져 있어 없는 줄 알았는데,
# 실제 템플릿 JSON 을 보니 composition_3 의 Subtitles-MDV 만 `"dynamic": true` 가 누락돼
# 예시에서 제외됐던 것이다. 그 결과 3번 장면에만 자막 스타일(폰트/색)이 주입되지 않아
# 템플릿 기본값(Montserrat/흰색)으로 렌더되는 버그가 있었다.
# → 전 장면 수에 MDV 를 포함한다. 슬롯 순서: 1=6K5 2=JTM 3=MDV 4=5Z2 5=D6M 6=3KT 7=6PM 8=3P6
SCENE_COUNT_CONFIG: dict = {
    4: {
        "template_id_prod": "0e8036d2-04d3-436c-8c02-7b8708a85f06",
        "template_id_test": "0e8036d2-04d3-436c-8c02-7b8708a85f06",
        "subtitle_suffixes": ["6K5", "JTM", "MDV", "5Z2"],
    },
    5: {
        # 현행 운영 템플릿 (기존 동작 100% 유지)
        "template_id_prod": "cab85e50-1e78-41b8-9644-80a061d349f6",
        "template_id_test": "eda9d421-b086-4660-9f3c-9236d826226f",
        "subtitle_suffixes": ["6K5", "JTM", "MDV", "5Z2", "D6M"],
    },
    6: {
        "template_id_prod": "5e530b01-2f3d-428e-b6d6-70a001703550",
        "template_id_test": "5e530b01-2f3d-428e-b6d6-70a001703550",
        "subtitle_suffixes": ["6K5", "JTM", "MDV", "5Z2", "D6M", "3KT"],
    },
    7: {
        "template_id_prod": "ffcddeb1-55da-4276-8998-b67fc2f92a82",
        "template_id_test": "ffcddeb1-55da-4276-8998-b67fc2f92a82",
        "subtitle_suffixes": ["6K5", "JTM", "MDV", "5Z2", "D6M", "3KT", "6PM"],
    },
    8: {
        "template_id_prod": "37229115-682d-41d5-b1f1-20953367b416",
        "template_id_test": "37229115-682d-41d5-b1f1-20953367b416",
        "subtitle_suffixes": ["6K5", "JTM", "MDV", "5Z2", "D6M", "3KT", "6PM", "3P6"],
    },
}


class SceneCountTemplateNotConfiguredError(Exception):
    """해당 장면 수의 Creatomate 템플릿이 아직 등록되지 않았을 때."""


def normalize_scene_count(raw) -> int:
    """입력값을 유효한 장면 수로 정규화. 무효하면 DEFAULT_SCENE_COUNT.

    FE 가 안 보내거나(구버전) 이상한 값을 보내도 기존 동작(5개)으로 안전하게 흐른다.
    """
    if isinstance(raw, bool):
        return DEFAULT_SCENE_COUNT
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str):
        # 숫자 문자열만 허용 ("6" O / "6.5" X / "abc" X)
        try:
            value = int(raw.strip())
        except (TypeError, ValueError):
            return DEFAULT_SCENE_COUNT
    else:
        # float 등은 거부 — 4.7 이 4 로 잘려 조용히 통과하는 것을 막는다
        return DEFAULT_SCENE_COUNT
    if value not in ALLOWED_SCENE_COUNTS:
        return DEFAULT_SCENE_COUNT
    return value


def get_config(scene_count: int) -> dict:
    """장면 수별 설정 반환 (무효 값은 기본값으로 정규화)."""
    return SCENE_COUNT_CONFIG[normalize_scene_count(scene_count)]


def get_template_id(scene_count: int) -> Optional[str]:
    """ENV(production/그 외)에 맞는 Creatomate 템플릿 ID. 미등록이면 None."""
    config = get_config(scene_count)
    if os.environ.get("ENV") == "production":
        return config.get("template_id_prod")
    return config.get("template_id_test")


def get_subtitle_suffixes(scene_count: int) -> Optional[list]:
    """장면 수별 자막 element suffix 목록. 미등록이면 None (자막 주입 스킵)."""
    return get_config(scene_count).get("subtitle_suffixes")


def is_configured(scene_count: int) -> bool:
    """해당 장면 수로 실제 영상 생성이 가능한지 (템플릿 등록 여부)."""
    return bool(get_template_id(scene_count))


def available_scene_counts() -> list:
    """FE 노출용 — 각 장면 수의 사용 가능 여부 포함."""
    return [
        {
            "scene_count": n,
            "available": is_configured(n),
            "is_default": n == DEFAULT_SCENE_COUNT,
        }
        for n in ALLOWED_SCENE_COUNTS
    ]
