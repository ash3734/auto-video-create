"""나레이션 속도(배속) 선택 — 2026-08-29.

## 배속은 왜 tempo 값이 아니라 '상대값' 인가

유저 요청은 "영상 속도를 1배 / 0.7배 / 1.25배 로 고르고 싶다" 였다.
그런데 지금 나가는 영상은 이미 **Typecast tempo 1.4** 로 만들어진다
(`api/blog.py` 의 TTS_SPEED, 2026-08-05 Typecast 전환 때부터 고정).

유저가 말하는 "1배" 는 **지금 듣고 있는 그 속도**지 tempo 1.0 이 아니다.
1배를 tempo 1.0 으로 만들면 아무도 요청하지 않았는데 기존 유저 전원의 영상이
40% 느려지고, 요청한 사람조차 "1배인데 왜 느려졌지" 가 된다.

그래서 배속은 **현재 기본값(1.4) 에 곱하는 상대값**으로 둔다.
1배 = tempo 1.4 = 지금과 완전히 동일 → 고르지 않은 유저의 결과물이 바뀌지 않는다.

## 천장

Typecast `audio_tempo` 허용 범위가 0.5~2.0 이므로 상대값의 상한은
2.0 / 1.4 ≈ 1.43 이다. 1.5배를 노출하면 tempo 2.1 이 되어 잘리므로 넣지 않는다.
선택지를 늘릴 일이 생기면 이 계산을 먼저 확인할 것.

## 왜 목록을 코드에 두는가

voices.py 와 같은 이유다 — **검증**. 요청값을 그대로 믿으면 유저가 아무 숫자나
넣어 엉뚱한 길이의 영상으로 크레딧(1,000)을 태울 수 있다. 목록에 없으면 기본값으로
떨어뜨린다.
"""
from typing import Optional

# 현재 운영 중인 Typecast tempo. 이 값이 곧 "1배" 다.
# 바꾸면 모든 배속이 함께 움직이므로 신중할 것.
BASE_TEMPO = 1.4

# Typecast audio_tempo 허용 범위 (tts_typecast.MIN_TEMPO / MAX_TEMPO 와 같은 값)
MIN_TEMPO, MAX_TEMPO = 0.5, 2.0

# 화면에 노출되는 순서대로. value 는 기본값에 곱하는 상대 배속.
SPEEDS = [
    {"value": 0.7, "name": "0.7배", "description": "느리게"},
    {"value": 1.0, "name": "1배", "description": "기본"},
    {"value": 1.25, "name": "1.25배", "description": "빠르게"},
]

DEFAULT_SPEED = 1.0

_ALLOWED = {s["value"] for s in SPEEDS}


def available_speeds() -> list:
    """FE 노출용 목록. 어느 것이 기본값인지 함께 알려준다."""
    return [
        {
            "value": s["value"],
            "name": s["name"],
            "description": s["description"],
            "is_default": s["value"] == DEFAULT_SPEED,
        }
        for s in SPEEDS
    ]


def is_allowed(speed) -> bool:
    """허용 목록에 있는 배속인가.

    0.7 같은 값이 JSON 을 거치며 미세하게 흔들릴 수 있어 근사 비교한다.
    bool 은 int 의 하위 타입이라 True/False 가 1.0/0.0 으로 통과하는 걸 막는다.
    """
    if isinstance(speed, bool) or not isinstance(speed, (int, float)):
        return False
    return any(abs(float(speed) - a) < 1e-6 for a in _ALLOWED)


def normalize_speed(raw) -> float:
    """요청값을 허용된 배속으로 정규화. 무효하면 기본값(1배).

    근사로 일치한 값은 **목록의 정식 값으로 스냅해서** 돌려준다. 들어온 값을 그대로
    돌려주면 0.7000000001 같은 값이 로그와 비교식에 그대로 흘러다닌다.

    FE 가 안 보내거나(구버전) 목록에 없는 값을 보내도 기존 동작으로 안전하게 흐른다.
    조용히 떨어뜨리는 게 맞는 이유는 voice_id 와 같다 — 배속이 틀렸다고 영상 생성을
    막을 사안이 아니다.
    """
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return DEFAULT_SPEED
    for allowed in _ALLOWED:
        if abs(float(raw) - allowed) < 1e-6:
            return allowed
    return DEFAULT_SPEED


def to_tempo(speed) -> float:
    """상대 배속 → Typecast audio_tempo.

    허용 목록을 거친 값만 들어오지만, 상수를 잘못 고쳐도 API 가 거부하는 값이
    나가지 않도록 마지막에 한 번 더 범위 안으로 가둔다.
    """
    tempo = BASE_TEMPO * normalize_speed(speed)
    return max(MIN_TEMPO, min(MAX_TEMPO, tempo))
