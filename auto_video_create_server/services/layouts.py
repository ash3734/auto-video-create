"""화면 배치(레이아웃) — 렌더에 쓸 템플릿 JSON 을 코드에서 고른다 (2026-10-05, 백로그 5-2·2-1).

## 왜 코드로 옮겼나

PO 가 한국 쇼츠에서 흔한 배치를 여러 개 템플릿으로 만들고 싶어 한다. 그런데 Creatomate
템플릿은 장면 수(4~8)마다, prod/test(워터마크 유무)마다 따로라 **배치 하나에 10개**다.
에디터에서 손으로 만들면 배치 7개에 70개가 된다.

Creatomate 는 저장된 템플릿 ID 대신 **템플릿 JSON 자체(source)** 를 렌더 요청에
실어 보내도 똑같이 렌더한다 (2026-10-05 test 5장면으로 확인: 한글 폰트·자동 자막·
modifications 모두 정상). 그래서 배치를 코드로 정의하고, 장면 수별 변형은 코드가 만든다.

## 1단계: 지금 배치(letterbox)는 "그대로 복사"

지금 쓰는 템플릿 10개를 `layout_sources/letterbox/` 에 **그대로** 저장했다
(scripts/snapshot_templates.py). 새로 생성하지 않은 이유: 10개 템플릿이 손으로 고쳐지며
조금씩 어긋나 있다 — 예를 들어 1번 장면만 자막 나눔 방식(`transcript_split`)이 다르다.
코드로 "깨끗하게" 다시 만들면 유저의 영상이 조용히 바뀐다. 복사본이면 바이트 단위로 같다.

## 주의 — 에디터 수정은 더 이상 반영되지 않는다

이제 렌더는 이 파일들을 쓴다. Creatomate 에디터에서 템플릿을 고쳤다면
`python3 scripts/snapshot_templates.py` 로 다시 가져와 배포해야 한다.
`--check` 로 어긋남을 확인할 수 있다.
"""
from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from typing import Optional

SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout_sources")

DEFAULT_LAYOUT = "letterbox"

# 화면에 노출할 배치 목록. 새 배치는 여기에 추가한다.
#   snapshot  — layout_sources/{id}/{env}_{n}.json 을 그대로 쓴다 (에디터에서 만든 것)
#   builder   — 코드가 장면 수만큼 만든다 (_BUILDERS)
LAYOUTS = {
    "letterbox": {
        "name": "기본",
        "description": "위 제목 · 가운데 사진 · 아래 자막",
        "kind": "snapshot",
    },
    "blur_fill": {
        "name": "흐린 배경",
        "description": "같은 사진을 흐리게 깔아 화면을 꽉 채우고, 원본은 자르지 않음",
        "kind": "builder",
    },
}


def _env_key() -> str:
    # scene_counts.get_template_id 와 같은 기준 — prod 에 워터마크(test) 템플릿이 나가면 안 된다.
    return "prod" if os.environ.get("ENV") == "production" else "test"


def normalize_layout(raw) -> str:
    """요청값을 허용된 배치로. 모르는 값이면 기본 배치 — 영상 생성을 막을 사안이 아니다."""
    return raw if isinstance(raw, str) and raw in LAYOUTS else DEFAULT_LAYOUT


@lru_cache(maxsize=64)
def _load(layout_id: str, env: str, scene_count: int) -> Optional[dict]:
    path = os.path.join(SOURCES_DIR, layout_id, f"{env}_{scene_count}.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)["source"]
    except (OSError, ValueError, KeyError) as e:
        print(f"[layouts] 템플릿 JSON 을 못 읽음 {path}: {e}")
        return None


def get_source(layout_id, scene_count: int) -> Optional[dict]:
    """렌더에 실어 보낼 템플릿 JSON. 없으면 None (호출하는 쪽이 template_id 로 대신 렌더).

    캐시된 원본을 돌려주면 호출하는 쪽이 고쳤을 때 다음 요청까지 오염되므로 복사본을 준다.
    """
    layout_id = normalize_layout(layout_id)
    env, n = _env_key(), int(scene_count)
    try:
        if LAYOUTS[layout_id]["kind"] == "builder":
            src = _BUILDERS[layout_id](env, n)
        else:
            src = _load(layout_id, env, n)
    except Exception as e:
        # 만들다 실패하면 기본 배치로 — 배치 때문에 영상 생성이 실패하면 안 된다.
        print(f"[layouts] {layout_id} 생성 실패 → 기본 배치: {e}")
        src = _load(DEFAULT_LAYOUT, env, n)
    return copy.deepcopy(src) if src is not None else None


def extra_modifications(layout_id, variables: dict, scene_count: int) -> dict:
    """배치마다 필요한 추가 값. 공통 코드(api/blog.py)는 배치를 모른 채 image{N} 등만 채운다.

    blur_fill: 장면 사진을 배경(bg{N})에도 한 번 더 깐다. 영상 장면은 배경을 끈다 —
    영상을 두 번 디코딩하면 렌더가 느려지고, 어두운 바탕으로도 충분하다.
    """
    if normalize_layout(layout_id) != "blur_fill":
        return {}
    out = {}
    for i in range(1, int(scene_count) + 1):
        src = variables.get(f"image{i}.source")
        shown = str(variables.get(f"image{i}.visible", "")).lower() == "true"
        if src and shown:
            out[f"bg{i}.source"] = src
            out[f"bg{i}.visible"] = "true"
        else:
            out[f"bg{i}.visible"] = "false"
    return out


# ── 코드로 만드는 배치 ────────────────────────────────────────────────────────

def _find(el: dict, name: str) -> Optional[dict]:
    for e in el.get("elements") or []:
        if e.get("name") == name:
            return e
        got = _find(e, name)
        if got:
            return got
    return None


def _clean(e: dict) -> dict:
    """에디터가 붙인 id·dynamic 은 렌더에 필요 없다."""
    return {k: copy.deepcopy(v) for k, v in e.items() if k not in ("id", "dynamic", "elements")}


_END_FADE = [{"time": "end", "type": "fade", "duration": 0.1, "reversed": True}]


def _common_parts(env: str) -> dict:
    """기본 배치에서 배치와 무관한 부품을 가져온다 — 폰트, 배경음악, 자막·제목 글꼴, 워터마크.

    새 배치도 같은 폰트 자산·같은 배경음악 요소(Audio-6FR)·같은 워터마크를 써야
    음악 선택(music.py)·자막 스타일 설정이 그대로 먹고, prod/test 구분도 그대로 간다.
    자막은 2번 장면 것을 기준으로 삼는다 — 10개 템플릿에서 가장 많이 쓰인 형태다
    (1번 장면만 transcript_split 이 달랐다).
    """
    base = _load(DEFAULT_LAYOUT, env, 5)
    return {
        "fonts": copy.deepcopy(base.get("fonts") or []),
        "bgm": _clean(_find(base, "Audio-6FR")),
        "subtitle": _clean(_find(base, "Subtitles-JTM")),
        "title": _clean(_find(base, "title")),
        "image_placeholder": _find(base, "image2")["source"],
        "video_placeholder": _find(base, "video2")["source"],
        "audio_placeholder": _find(base, "audio1")["source"],
        "watermark": _clean(_find(base, "Text-4DM")) if _find(base, "Text-4DM") else None,
    }


def _build_blur_fill(env: str, n: int) -> dict:
    """흐린 배경 꽉 채움형.

    블로그 사진은 가로·정사각이 많아, 세로 화면을 꽉 채우려면 잘라야 한다. 그러면
    사진 잘림 수정(scene_media.py, fit=contain) 이 무의미해진다. 같은 사진을 흐리고
    어둡게 깔아 화면을 채우고, 원본은 가운데에 통째로 놓는다.

    세로 위치 (720×1280 기준):
      제목  11% — 테두리를 둘러 흐린 사진 위에서도 읽히게
      사진  44% 중심, 높이 46% (20%~67%)
      자막  76% — 유튜브 아래쪽 채널명·설명 영역(대략 하단 20%) 위
    """
    from .scene_counts import SCENE_COUNT_CONFIG

    parts = _common_parts(env)
    suffixes = SCENE_COUNT_CONFIG[n]["subtitle_suffixes"]
    photo_box = {"x": "50%", "y": "44%", "width": "100%", "height": "46%"}

    elements = [parts["bgm"]]
    for i in range(1, n + 1):
        sub = dict(parts["subtitle"])
        sub.update({"name": f"Subtitles-{suffixes[i - 1]}", "track": 5, "time": 0,
                    "y": "76%", "transcript_source": f"audio{i}"})
        comp = {
            "name": f"composition_{i}", "type": "composition", "track": 2,
            "fill_color": "#111111",
            "elements": [
                {"name": f"bg{i}", "type": "image", "track": 1, "time": 0,
                 "source": parts["image_placeholder"], "fit": "cover",
                 "width": "100%", "height": "100%",
                 "blur_radius": 30, "color_overlay": "rgba(0,0,0,0.35)", "visible": False},
                {"name": f"image{i}", "type": "image", "track": 2, "time": 0,
                 "source": parts["image_placeholder"], "fit": "contain", "visible": False, **photo_box},
                {"name": f"video{i}", "type": "video", "track": 3, "time": 0, "loop": True,
                 "duration": None, "source": parts["video_placeholder"], **photo_box},
                {"name": f"audio{i}", "type": "audio", "track": 4, "time": 0,
                 "source": parts["audio_placeholder"]},
                sub,
            ],
        }
        if i == 1:
            comp["time"] = 0
        if i == n:
            comp["animations"] = copy.deepcopy(_END_FADE)
        elements.append(comp)

    title = dict(parts["title"])
    title.update({"y": "11%", "height": "12%", "stroke_color": "#000000", "stroke_width": "1.2 vmin"})
    elements.append({"name": "composition_title", "type": "composition", "track": 3, "time": 0,
                     "animations": copy.deepcopy(_END_FADE), "elements": [title]})
    if parts["watermark"]:
        wm = dict(parts["watermark"])
        wm["track"] = 4
        elements.append(wm)

    return {"output_format": "mp4", "width": 720, "height": 1280,
            "fonts": parts["fonts"], "elements": elements}


_BUILDERS = {
    "blur_fill": _build_blur_fill,
}
