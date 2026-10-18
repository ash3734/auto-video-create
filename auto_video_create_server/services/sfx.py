"""효과음 — 어디에 어떤 소리를 넣을지 AI 가 정한다 (2026-10-18, 백로그 3-5).

## 유저가 정하는 것 / AI 가 정하는 것 (2026-10-19 PO)
유저는 켤지 말지만 정한다 ("none" / "auto"). 켜면 대본을 보고 **어느 장면 전환에, 어떤
소리를** 넣을지 AI 가 정한다 (plan_sounds). 처음엔 유저가 소리 종류를 고르고 모든 장면
전환에 똑같이 넣었는데, PO 가 원한 건 이게 아니었다.

정할 수 있는 단위는 **장면 경계**다. 단어가 몇 초에 나오는지는 우리가 모른다 (자막은
Creatomate 가 음성을 받아써서 만든다). 그래서 "3번 장면이 시작할 때 띵" 까지가 해상도다.

AI 계획을 못 받으면(시간 초과·실패) 기본 규칙으로 간다 — 2번 장면부터 장면마다 "휙".
끝 화면이 있으면 그 시작에는 항상 "띵" (마무리 신호).

## 어디에 넣지 않나
1번 장면 시작 — 영상이 효과음으로 시작하면 첫마디가 묻힌다.

## 음원과 라이선스 (music.py 와 같은 방식)
Pixabay 효과음, Pixabay Content License (상업적 이용 가능, 출처 표기 불필요, 파일 자체의
재배포는 금지). 그래서 비공개 버킷에 두고 렌더할 때마다 만료되는 주소(presigned)로만
Creatomate 에 넘긴다. 네 곡 모두 같은 제작자(DRAGON-STUDIO)라 소리 결이 비슷하다.

## 크기
나레이션(100%)을 덮지 않고 배경음악(15%)보다는 또렷하게 — 45%.
"""
from __future__ import annotations

import copy
import re
from typing import Optional

from utils.s3_utils import s3_client

BUCKET = "blog-to-short-form-credits"   # 비공개. music.py 와 같은 버킷
PREFIX = "sfx"
URL_EXPIRES = 3600                       # 렌더 접수 뒤 Creatomate 가 받아갈 때까지
VOLUME = "45%"

_LICENSE = "Pixabay Content License"

SOUNDS = {
    "none": {"name": "없음", "description": "효과음 없이"},
    "whoosh": {"name": "휙", "description": "바람 가르는 소리", "title": "Simple Whoosh",
               "artist": "DRAGON-STUDIO",
               "source_page": "https://pixabay.com/sound-effects/film-special-effects-simple-whoosh-382724/",
               "cdn": "https://cdn.pixabay.com/download/audio/2025/07/30/audio_b3087a581e.mp3"},
    "swipe": {"name": "스윽", "description": "화면 넘기는 소리", "title": "Quick Swipe",
              "artist": "DRAGON-STUDIO",
              "source_page": "https://pixabay.com/sound-effects/film-special-effects-quick-swipe-405450/",
              "cdn": "https://cdn.pixabay.com/download/audio/2025/09/16/audio_5337b3b272.mp3"},
    "pop": {"name": "톡", "description": "가볍게 튀는 소리", "title": "Pop",
            "artist": "DRAGON-STUDIO",
            "source_page": "https://pixabay.com/sound-effects/film-special-effects-pop-402324/",
            "cdn": "https://cdn.pixabay.com/download/audio/2025/09/09/audio_3023b9bde2.mp3"},
    "ding": {"name": "띵", "description": "맑은 알림 소리", "title": "Ding",
             "artist": "DRAGON-STUDIO",
             "source_page": "https://pixabay.com/sound-effects/film-special-effects-ding-402325/",
             "cdn": "https://cdn.pixabay.com/download/audio/2025/09/09/audio_2556e69436.mp3"},
}
for _k, _v in SOUNDS.items():
    if _k != "none":
        _v.setdefault("license", _LICENSE)
DEFAULT_SOUND = "none"

_SCENE = re.compile(r"^composition_(\d+)$")

AUTO = "auto"
OUTRO_SOUND = "ding"
FALLBACK_SOUND = "whoosh"
# 화면에 보이는 선택지는 이 둘뿐이다. 소리 종류(whoosh 등)는 AI 가 고른다.
CHOICES = {
    "none": {"name": "없음", "description": "효과음 없이"},
    AUTO: {"name": "자동", "description": "대본을 보고 어울리는 곳에 AI가 넣어요"},
}
_SOUND_IDS = [k for k in SOUNDS if k != "none"]


def normalize_sound(raw) -> str:
    """auto / none, 그리고 (예전 화면이 보내는) 소리 이름. 모르는 값은 none."""
    if raw == AUTO:
        return AUTO
    return raw if isinstance(raw, str) and raw in SOUNDS else DEFAULT_SOUND


def clean_plan(raw, n: int) -> list:
    """장면 n 개에 대한 계획 → 길이 n 리스트 (장면 시작마다 소리 이름 또는 None).

    1번 장면은 항상 None. 너무 자주 울리면 시끄러워서 절반(올림)까지만 남긴다.
    """
    out = [None] * n
    items = raw if isinstance(raw, list) else []
    for i, v in enumerate(items[:n]):
        if i > 0 and isinstance(v, str) and v in _SOUND_IDS:
            out[i] = v
    limit = (n + 1) // 2
    kept = 0
    for i in range(n):
        if out[i]:
            kept += 1
            if kept > limit:
                out[i] = None
    return out


def default_plan(n: int) -> list:
    return [None] + [FALLBACK_SOUND] * (n - 1)


PLAN_MODEL = "gpt-4.1-mini"
PLAN_TIMEOUT_SECONDS = 10
PLAN_PROMPT = """쇼츠 영상의 장면별 나레이션이야. 장면이 바뀌는 순간에 넣을 효과음을 정해줘.
쓸 수 있는 소리:
- whoosh: 휙 — 분위기가 바뀌거나 속도감 있게 넘어갈 때
- swipe: 스윽 — 다음 항목·다음 장소로 넘어갈 때
- pop: 톡 — 새로운 것이 등장하거나 가볍고 귀여운 포인트
- ding: 띵 — 핵심·정답·가격·추천처럼 강조할 때
규칙:
- 각 장면이 "시작될 때" 울린다. 1번 장면에는 넣지 않는다.
- 꼭 필요한 곳에만. 장면 수의 절반을 넘기지 않는다. 같은 소리만 반복하지 않는다.
- 넣지 않는 장면은 "none".
JSON 하나만 출력: {"sounds": ["none", "<2번 장면>", "<3번 장면>", ...]} (장면 수와 같은 길이)

장면:
"""


def plan_sounds(scripts) -> list:
    """대본을 보고 장면별 효과음 계획. 실패하면 기본 규칙(default_plan)."""
    scripts = [str(x or "").strip() for x in (scripts or [])]
    n = len(scripts)
    if n == 0:
        return []
    try:
        import json
        import os
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=PLAN_TIMEOUT_SECONDS, max_retries=0)
        body = "\n".join(f"{i}. {t[:200]}" for i, t in enumerate(scripts, 1))
        resp = client.chat.completions.create(
            model=PLAN_MODEL,
            messages=[{"role": "user", "content": PLAN_PROMPT + body}],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.3,
        )
        raw = json.loads(resp.choices[0].message.content or "{}").get("sounds")
        if not isinstance(raw, list):
            raise ValueError(f"sounds 가 없음: {raw!r}")
        return clean_plan(raw, n)
    except Exception as e:
        print(f"[sfx] 효과음 계획 실패 — 기본 규칙으로: {e}")
        return default_plan(n)


def s3_key(sound_id: str) -> str:
    return f"{PREFIX}/{sound_id}.mp3"


def render_url(sound_id: str) -> Optional[str]:
    """렌더용 주소. 파일이 없으면 None — 없는 주소를 넘기면 Creatomate 가 렌더 전체를 실패시킨다.

    presigned 주소는 파일이 없어도 만들어지므로 먼저 있는지 확인한다 (head 한 번, 수십 ms).
    """
    try:
        c = s3_client()
        c.head_object(Bucket=BUCKET, Key=s3_key(sound_id))
        return c.generate_presigned_url(
            "get_object", Params={"Bucket": BUCKET, "Key": s3_key(sound_id)}, ExpiresIn=URL_EXPIRES)
    except Exception as e:
        print(f"[sfx] 효과음 주소를 못 만듦 — 소리 없이 진행 {sound_id}: {e}")
        return None


def _audio(url: str) -> dict:
    return {"name": "sfx", "type": "audio", "track": 9, "time": 0, "source": url, "volume": VOLUME}


def apply(source: dict, sound=None, plan=None) -> dict:
    """효과음을 넣은 사본. 고른 게 없거나 파일 주소를 못 만들면 그 소리는 빠진다.

    sound="auto"  → plan(장면 시작마다 소리 이름/None)대로. plan 이 없으면 기본 규칙.
    sound=소리 이름 → 예전 방식: 2번 장면부터 장면마다 그 소리 (예전 화면 호환).
    끝 화면이 있으면 그 시작에 마무리 소리 (auto 면 띵, 소리 이름이면 그 소리).
    """
    sound = normalize_sound(sound)
    src = copy.deepcopy(source)
    if sound == "none":
        return src
    scenes = [c for c in src.get("elements") or [] if _SCENE.match(c.get("name") or "")]
    n = len(scenes)
    if sound == AUTO:
        steps = clean_plan(plan, n) if plan else default_plan(n)
        outro_sound = OUTRO_SOUND
    else:
        steps = [None] + [sound] * (n - 1)
        outro_sound = sound

    urls = {}

    def url_for(sid):
        if sid not in urls:
            urls[sid] = render_url(sid)       # 파일이 없으면 None — 그 소리만 빠진다
        return urls[sid]

    for comp, sid in zip(scenes, steps):
        if sid and url_for(sid):
            comp.setdefault("elements", []).append(_audio(url_for(sid)))
    for comp in src.get("elements") or []:
        if comp.get("name") == "composition_outro" and url_for(outro_sound):
            comp.setdefault("elements", []).append(_audio(url_for(outro_sound)))
    return src


def available_sounds() -> list:
    """화면용 선택지 — 없음 / 자동. 소리 종류는 AI 가 고르므로 보여주지 않는다."""
    return [{"id": k, "name": v["name"], "description": v["description"], "is_default": k == DEFAULT_SOUND,
             "preview_url": None} for k, v in CHOICES.items()]
