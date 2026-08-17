"""선택 가능한 나레이션 음성 목록 — 2026-08-17.

## 왜 코드에 목록을 두는가

Typecast 계정에는 ssfm-v30 음성만 590개가 있고, **API 응답에 언어 필드가 없다**
(`voice_id / voice_name / model / emotions / voice_type` 뿐). 한국어 음성을 골라내려면
사람이 들어봐야 한다. 그래서 PO 가 직접 듣고 고른 것만 여기에 둔다.

목록을 코드에 두는 두 번째 이유는 **검증**이다. 요청의 voice_id 를 그대로 믿으면
유저가 아무 ID나 넣어 영어 음성으로 크레딧(1,000)을 태울 수 있다. 허용 목록에 없으면
기본값으로 떨어뜨린다.

## 기본값

`DEFAULT_VOICE_ID` 는 혜리(Hyelee)다. 2026-08-05 Typecast 전환 이후 나간 모든 영상이
이 목소리이므로, 음성을 고르지 않은 기존 유저의 결과물이 바뀌면 안 된다.
"""
from typing import Optional

from .tts_typecast import DEFAULT_VOICE_ID as _TTS_DEFAULT_VOICE_ID

# 화면에 노출되는 순서대로. name 은 한글 표시명, description 은 PO 가 샘플을 듣고 정한 한 줄.
# (Typecast 의 voice_name 은 Hyelee / Sanghyun 같은 로마자라 그대로 쓰지 않는다)
VOICES = [
    {
        "voice_id": "tc_62e8f21e979b3860fe2f6a24",
        "name": "혜리",
        "description": "밝은 여성",
        "typecast_name": "Hyelee",
    },
    {
        "voice_id": "tc_69fc0cff784968297fb45daa",
        "name": "상현",
        "description": "밝은 남성",
        "typecast_name": "Sanghyun",
    },
    {
        "voice_id": "tc_694395d43f2c8d9d43e9a897",
        "name": "병훈",
        "description": "나이 있는 남성",
        "typecast_name": "Byunghun",
    },
    {
        "voice_id": "tc_6059dad0b83880769a50502f",
        "name": "창수",
        "description": "재미있는 남성",
        "typecast_name": "Changsu",
    },
    {
        "voice_id": "tc_66ab0e26ec23f325b7ad51df",
        "name": "예슬",
        "description": "아나운서 여성",
        "typecast_name": "Yeseul",
    },
]

# 전환 이전부터 쓰던 음성. 미선택 유저의 결과물이 바뀌지 않도록 여기에 묶어 둔다.
DEFAULT_VOICE_ID = _TTS_DEFAULT_VOICE_ID

_BY_ID = {v["voice_id"]: v for v in VOICES}


def available_voices() -> list:
    """FE 노출용 목록. 어느 것이 기본값인지 함께 알려준다."""
    return [
        {
            "voice_id": v["voice_id"],
            "name": v["name"],
            "description": v["description"],
            "is_default": v["voice_id"] == DEFAULT_VOICE_ID,
        }
        for v in VOICES
    ]


def is_allowed(voice_id) -> bool:
    return isinstance(voice_id, str) and voice_id in _BY_ID


def normalize_voice_id(raw) -> str:
    """요청값을 허용된 voice_id 로 정규화. 무효하면 기본값.

    FE 가 안 보내거나(구버전) 목록에 없는 ID 를 보내도 기존 동작(혜리)으로 안전하게
    흐른다. 조용히 떨어뜨리는 게 맞는 이유는, 음성이 틀렸다고 영상 생성을 막을 만한
    사안이 아니기 때문이다.
    """
    if is_allowed(raw):
        return raw
    return DEFAULT_VOICE_ID


def get_voice(voice_id) -> Optional[dict]:
    return _BY_ID.get(voice_id)
