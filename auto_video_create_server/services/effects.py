"""화면 효과 — 사진 움직임 · 장면 전환 (2026-10-18, 백로그 3-7).

배치(layouts.py)와 따로 둔다. 효과는 어떤 배치에도 똑같이 얹히는 것이라, 배치마다
다시 만들지 않고 렌더 직전에 템플릿 JSON 에 애니메이션만 덧붙인다. 배치들은 모두
같은 이름 규칙(image{N}, composition_{N})을 지키므로 여기서 이름으로 찾아 붙인다.

## 사진 움직임 (motion)
  none  지금 그대로 (기본값 — 안 고른 유저의 결과물은 바뀌지 않는다)
  zoom  장면마다 사진이 천천히 확대된다 (켄 번즈). 영상 장면에는 넣지 않는다 —
        이미 움직이는 화면을 또 키우면 어지럽다.

## 장면 전환 (transition)
  none   지금 그대로 (기본값)
  fade   다음 장면이 부드럽게 나타난다
  slide  다음 장면이 옆에서 밀려 들어온다
  punch  다음 장면이 살짝 크게 시작해 제자리로 — 화면을 바로 덮어 빈 바탕이 안 보인다

Creatomate 의 진짜 "전환"(transition: true)은 두 장면을 겹쳐 그 만큼 영상을 줄인다.
우리 장면은 장면마다 나레이션 음성이 들어 있어서, 겹치면 **앞 장면 말끝과 다음 장면
첫마디가 동시에 들린다.** 그래서 겹치지 않는 "등장" 애니메이션으로 만든다 —
장면은 그대로 이어지고, 새 장면이 들어오는 첫 0.35초만 움직인다.
"""
from __future__ import annotations

import copy
import re

MOTIONS = {
    "none": {"name": "없음", "description": "지금처럼 사진이 멈춰 있어요"},
    "zoom": {"name": "천천히 확대", "description": "장면마다 사진이 천천히 다가와요"},
}
TRANSITIONS = {
    "none": {"name": "없음", "description": "장면이 바로 바뀌어요"},
    "fade": {"name": "부드럽게", "description": "다음 장면이 스르르 나타나요"},
    "slide": {"name": "밀어서", "description": "다음 장면이 옆에서 밀려 들어와요"},
    "punch": {"name": "다가오며", "description": "다음 장면이 확 다가오며 바뀌어요"},
}
DEFAULT_MOTION = "none"
DEFAULT_TRANSITION = "none"

# 확대 폭. 크면 사진 가장자리가 많이 잘리고(contain 으로 지킨 "안 자름"과 부딪힌다),
# 작으면 움직이는 줄 모른다. 8% 면 장면 하나(3~5초) 동안 눈에 띄면서 잘림은 가장자리뿐이다.
ZOOM_END = "108%"
TRANSITION_SECONDS = 0.35

_SCENE = re.compile(r"^composition_(\d+)$")


def normalize_motion(raw) -> str:
    return raw if isinstance(raw, str) and raw in MOTIONS else DEFAULT_MOTION


def normalize_transition(raw) -> str:
    return raw if isinstance(raw, str) and raw in TRANSITIONS else DEFAULT_TRANSITION


def _zoom():
    # 프리셋은 "효과 → 원래" 방향(등장)이다. start 100% → end 108% 로 두고 time 을 비우면
    # 요소 전체 길이에 걸쳐 커진다. fade 는 기본이 켜져 있어 꺼야 깜빡이지 않는다.
    return {"type": "scale", "scope": "element", "start_scale": "100%", "end_scale": ZOOM_END,
            "easing": "linear", "fade": False}


def _entrance(kind: str):
    # fade·slide 는 들어오는 동안 뒤의 검은 바탕이 잠깐 보인다 (앞 장면은 이미 끝났으므로).
    # fade 는 "검게 갔다 밝아지는" 연출로 읽히지만, slide 는 빈 띠가 보인다 — 2026-10-18
    # 샘플에서 확인. punch 는 첫 프레임부터 화면을 덮어 빈 바탕이 없다.
    if kind == "fade":
        return {"type": "fade", "time": "start", "duration": TRANSITION_SECONDS}
    if kind == "punch":
        return {"type": "scale", "time": "start", "duration": TRANSITION_SECONDS,
                "start_scale": "115%", "end_scale": "100%", "fade": False, "easing": "quadratic-out"}
    # 왼쪽(180°)에서 오른쪽으로 들어온다. fade 를 끄면 뒤의 빈 바탕이 덜 비친다.
    return {"type": "slide", "time": "start", "duration": TRANSITION_SECONDS,
            "direction": "180°", "distance": "100%", "fade": False, "easing": "quadratic-out"}


def apply(source: dict, motion=None, transition=None, variables=None) -> dict:
    """템플릿 JSON 에 효과 애니메이션을 덧붙인 사본을 돌려준다 (원본은 건드리지 않음).

    variables 는 렌더에 실릴 modifications — 영상 장면(image{N}.visible == false)을
    가려내 확대를 빼는 데 쓴다.
    """
    motion, transition = normalize_motion(motion), normalize_transition(transition)
    src = copy.deepcopy(source)
    if motion == "none" and transition == "none":
        return src
    variables = variables or {}

    for comp in src.get("elements") or []:
        m = _SCENE.match(comp.get("name") or "")
        if not m:
            continue
        i = int(m.group(1))
        if transition != "none" and i > 1:          # 첫 장면은 영상 시작이라 그대로
            comp.setdefault("animations", []).insert(0, _entrance(transition))
        if motion == "zoom":
            photo_scene = str(variables.get(f"image{i}.visible", "true")).lower() == "true"
            for el in comp.get("elements") or []:
                if el.get("name") == f"image{i}" and photo_scene:
                    el.setdefault("animations", []).append(_zoom())
    return src
