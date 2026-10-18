"""효과음 — 장면이 바뀔 때마다 짧은 소리 (2026-10-18, 백로그 3-5).

장면 전환(effects.py)과 짝이다. 전환 애니메이션이 없어도 소리만 넣을 수 있다.
기본값은 "none" — 안 고른 유저의 결과물은 바뀌지 않는다.

## 어디에 넣나
2번 장면부터 각 장면의 시작(0초)에 한 번, 끝 화면(bookends.py)이 있으면 그 시작에도
한 번. 1번 장면에는 넣지 않는다 — 영상이 "휙" 소리로 시작하면 첫마디가 묻힌다.

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


def normalize_sound(raw) -> str:
    return raw if isinstance(raw, str) and raw in SOUNDS else DEFAULT_SOUND


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


def apply(source: dict, sound=None) -> dict:
    """장면 시작마다 효과음을 넣은 사본. 고른 게 없거나 주소를 못 만들면 원본 그대로의 사본."""
    sound = normalize_sound(sound)
    src = copy.deepcopy(source)
    if sound == "none":
        return src
    url = render_url(sound)
    if not url:
        # 효과음 때문에 영상 생성이 실패하면 안 된다 — 소리 없이 간다.
        return src
    for comp in src.get("elements") or []:
        name = comp.get("name") or ""
        m = _SCENE.match(name)
        if (m and int(m.group(1)) > 1) or name == "composition_outro":
            comp.setdefault("elements", []).append(_audio(url))
    return src


PREVIEW_EXPIRES = 600


def available_sounds() -> list:
    """화면용 목록. 미리듣기 주소는 10분 뒤 만료 — 화면을 열 때마다 새로 받는다."""
    out = []
    for k, v in SOUNDS.items():
        row = {"id": k, "name": v["name"], "description": v["description"], "is_default": k == DEFAULT_SOUND,
               "preview_url": None}
        if k != "none":
            try:
                row["preview_url"] = s3_client().generate_presigned_url(
                    "get_object", Params={"Bucket": BUCKET, "Key": s3_key(k)}, ExpiresIn=PREVIEW_EXPIRES)
            except Exception as e:
                print(f"[sfx] 미리듣기 주소 실패 {k}: {e}")
        out.append(row)
    return out
