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

# 배치 미리보기 이미지 (scripts/render_layout_previews.py 가 만든다). 우리가 만든 샘플이라
# 공개 버킷에 둔다. 새 배치를 추가하면 그 스크립트를 다시 돌려야 미리보기가 생긴다.
PREVIEW_BASE = "https://auto-video-tts-files.s3.ap-northeast-2.amazonaws.com/static/layout-previews"


def preview_url(layout_id: str) -> str:
    return f"{PREVIEW_BASE}/{layout_id}.jpg"

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
    "hook": {
        "name": "후킹 문구",
        "description": "위에 큰 제목 한 줄, 아래 사진 — 첫눈에 꽂히게",
        "kind": "builder",
    },
    "info_card": {
        "name": "맛집 정보카드",
        "description": "아래에 가게 이름·위치·가격 카드 — 체험단 맛집 후기에",
        "kind": "builder",
    },
    "news": {
        "name": "뉴스형",
        "description": "밝은 배경에 헤드라인·사진·요약 자막 — 정보 전달에",
        "kind": "builder",
    },
    "fullscreen": {
        "name": "풀스크린",
        "description": "사진이 화면 전체를 채움 — 가로 사진은 양옆이 잘려요",
        "kind": "builder",
    },
    "sns_feed": {
        "name": "SNS 피드",
        "description": "인스타 게시물처럼 프로필·사진·하트 — 일상·감성 글에",
        "kind": "builder",
    },
}

# 정보카드 배치에 넣는 값 (요청의 place_*). 비어 있으면 카드를 숨긴다.
PLACE_FIELDS = ("name", "location", "price")
PLACE_MAX = 30


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


def extra_modifications(layout_id, variables: dict, scene_count: int, context=None) -> dict:
    """배치마다 필요한 추가 값. 공통 코드(api/blog.py)는 배치를 모른 채 image{N} 등만 채운다.

    context: {"user_id": ..., "place": {"name","location","price"}} — 배치가 쓰는 부가 정보.

    blur_fill : 장면 사진을 배경(bg{N})에도 한 번 더 깐다. 영상 장면은 배경을 끈다 —
                영상을 두 번 디코딩하면 렌더가 느려지고, 어두운 바탕으로도 충분하다.
    fullscreen: 사진·영상을 화면 전체에 꽉 채운다 (fit=cover). 공통 코드는 사진 잘림을 막으려고
                fit=contain 을 넣으므로, 이 배치에서만 덮어쓴다 — 배치 설명에 잘린다고 적었다.
    sns_feed  : 프로필 이름을 @아이디 로.
    info_card : 가게 정보 카드. 셋 다 비면 카드를 숨긴다.
    """
    layout_id = normalize_layout(layout_id)
    context = context or {}
    out = {}
    n = int(scene_count)
    if layout_id == "blur_fill":
        for i in range(1, n + 1):
            src = variables.get(f"image{i}.source")
            shown = str(variables.get(f"image{i}.visible", "")).lower() == "true"
            if src and shown:
                out[f"bg{i}.source"] = src
                out[f"bg{i}.visible"] = "true"
            else:
                out[f"bg{i}.visible"] = "false"
    elif layout_id == "fullscreen":
        for i in range(1, n + 1):
            if f"image{i}.source" in variables:
                out[f"image{i}.fit"] = "cover"
            if f"video{i}.source" in variables:
                out[f"video{i}.fit"] = "cover"
    elif layout_id == "sns_feed":
        uid = str(context.get("user_id") or "").strip()
        out["profile_name.text"] = f"@{uid}" if uid else "@my_blog"
    elif layout_id == "info_card":
        place = clean_place(context.get("place"))
        if any(place.values()):
            out["place_name.text"] = place["name"] or " "
            out["place_location.text"] = f"위치  {place['location']}" if place["location"] else " "
            out["place_price.text"] = f"가격  {place['price']}" if place["price"] else " "
        else:
            out["place_card.visible"] = "false"
    return out


def clean_place(raw) -> dict:
    """요청의 가게 정보 정리 — 한 줄, 칸마다 PLACE_MAX 자."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for k in PLACE_FIELDS:
        v = raw.get(k)
        v = " ".join(str(v).split()) if isinstance(v, (str, int, float)) else ""
        out[k] = v[:PLACE_MAX]
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


# ── 공통 부품 (2026-10-18 배치 5종 추가) ─────────────────────────────────────
#
# 모든 배치가 지키는 것:
#   · 이름 규칙 — image{N}/video{N}/audio{N}/Subtitles-*/title/Audio-6FR. 공통 코드(api/blog.py)·
#     효과(effects.py)·끝 화면(bookends.py)·효과음(sfx.py)이 이 이름으로 찾아 붙는다.
#   · 자막과 제목은 **어두운 바탕 위**에 둔다. 글자 색은 유저가 자막 스타일에서 고르고(기본
#     흰 자막·노란 제목) 서버가 그대로 덮어쓰므로, 밝은 바탕에 두면 안 보인다.
#   · 자막은 화면 높이 80% 위 — 유튜브 아래쪽 채널명·설명 영역에 가리지 않게.
#   · 사진은 기본적으로 자르지 않는다 (fit=contain). 풀스크린만 예외이고 설명에 적었다.

_RECT = "M 0 0 L 100 0 L 100 100 L 0 100 L 0 0 Z"
_TEXT_FONT = "Noto Sans KR"     # 배치가 직접 쓰는 글자(라벨·카드). 유저 설정과 무관한 고정 글자.


def _rect(name, track, x, y, w, h, fill, radius=None, anchor=("50%", "50%"), time=0):
    # radius 는 px/vw/vh/vmin 만 받는다 — "%" 는 Creatomate 가 거부한다 (2026-10-18 확인).
    e = {"name": name, "type": "shape", "track": track, "time": time, "path": _RECT,
         "x": x, "y": y, "width": w, "height": h, "x_anchor": anchor[0], "y_anchor": anchor[1],
         "fill_color": fill}
    if radius:
        e["border_radius"] = radius
    return e


def _icon(name, track, x, y, size, path, stroke="#ffffff", fill="rgba(0,0,0,0)"):
    return {"name": name, "type": "shape", "track": track, "time": 0, "path": path,
            "x": x, "y": y, "width": size, "height": size, "x_anchor": "50%", "y_anchor": "50%",
            "fill_color": fill, "stroke_color": stroke, "stroke_width": "0.7 vmin"}


def _label(name, track, text, x, y, w, h, size, color, weight="700", align="50%", anchor_x="50%"):
    return {"name": name, "type": "text", "track": track, "time": 0, "text": text,
            "x": x, "y": y, "width": w, "height": h, "x_anchor": anchor_x, "y_anchor": "50%",
            "x_alignment": align, "y_alignment": "50%", "font_family": _TEXT_FONT,
            "font_weight": weight, "font_size": size, "fill_color": color}


def _media(i, parts, box, fit="contain"):
    """장면 하나의 사진·영상·음성. box = {"x","y","width","height"}."""
    return [
        {"name": f"image{i}", "type": "image", "track": 2, "time": 0,
         "source": parts["image_placeholder"], "fit": fit, "visible": False, **box},
        {"name": f"video{i}", "type": "video", "track": 3, "time": 0, "loop": True,
         "duration": None, "source": parts["video_placeholder"], "fit": fit, **box},
        {"name": f"audio{i}", "type": "audio", "track": 4, "time": 0,
         "source": parts["audio_placeholder"]},
    ]


def _subtitle(parts, suffix, i, **over):
    sub = dict(parts["subtitle"])
    sub.update({"name": f"Subtitles-{suffix}", "track": 6, "time": 0, "transcript_source": f"audio{i}"})
    sub.update(over)
    return sub


def _scene(i, n, fill, children):
    comp = {"name": f"composition_{i}", "type": "composition", "track": 2,
            "fill_color": fill, "elements": children}
    if i == 1:
        comp["time"] = 0
    if i == n:
        comp["animations"] = copy.deepcopy(_END_FADE)
    return comp


def _overlay(name, track, children):
    """영상 전체에 걸쳐 장면 위에 얹히는 층 (제목·틀·카드).

    한 층 안의 요소는 **트랙을 하나씩 따로** 준다 (적힌 순서 = 아래에서 위로). 같은 트랙에
    둘 이상 두면 Creatomate 는 그중 하나만 그린다 — 2026-10-18 미리보기에서 후킹 제목,
    카드의 가게 이름·위치, 뉴스 라벨·헤드라인 띠, SNS 프로필·아이콘이 통째로 빠졌다.
    """
    children = [dict(c, track=i) for i, c in enumerate(children, 1)]
    return {"name": name, "type": "composition", "track": track, "time": 0,
            "animations": copy.deepcopy(_END_FADE), "elements": children}


def _title(parts, **over):
    t = dict(parts["title"])
    t.update(over)
    return t


def _root(parts, elements):
    if parts["watermark"]:
        wm = dict(parts["watermark"])
        wm["track"] = max(e.get("track") or 1 for e in elements) + 1
        elements.append(wm)
    return {"output_format": "mp4", "width": 720, "height": 1280,
            "fonts": parts["fonts"], "elements": elements}


def _scenes(env, n, fill, children_for):
    from .scene_counts import SCENE_COUNT_CONFIG
    parts = _common_parts(env)
    suffixes = SCENE_COUNT_CONFIG[n]["subtitle_suffixes"]
    return parts, [parts["bgm"]] + [_scene(i, n, fill, children_for(i, suffixes[i - 1], parts))
                                     for i in range(1, n + 1)]


def _build_hook(env: str, n: int) -> dict:
    """후킹 문구형 — 위 1/3 을 큰 제목이 차지하고, 사진은 그 아래.

      제목 0~33% (자동 맞춤으로 크게) · 사진 34~71% · 자막 77%
    """
    box = {"x": "50%", "y": "52.5%", "width": "100%", "height": "37%"}
    parts, els = _scenes(env, n, "#000000", lambda i, suf, p: _media(i, p, box) + [
        _subtitle(p, suf, i, y="77%")])
    els.append(_overlay("composition_title", 3, [
        _title(parts, y="17%", width="92%", height="25%", stroke_color="#000000",
               stroke_width="1.4 vmin", font_size_maximum="20 vmin"),
        _rect("hook_line", 2, "50%", "32.6%", "16%", "0.5%", "#ffffff", radius="1 vmin"),
    ]))
    return _root(parts, els)


def _build_info_card(env: str, n: int) -> dict:
    """맛집 정보카드형 — 기본 배치 위에, 아래쪽에 가게 이름·위치·가격 카드.

      제목 띠 0~17% · 사진 18~54% · 자막 60.5% · 카드 67~83% (유튜브 하단 영역 위)
    카드 글자는 흰 카드 위 진한 색으로 고정 — 유저 자막 색과 무관하다.
    """
    box = {"x": "50%", "y": "36%", "width": "100%", "height": "36%"}
    parts, els = _scenes(env, n, "#1a1a1a", lambda i, suf, p: _media(i, p, box) + [
        _subtitle(p, suf, i, y="60.5%", width="86%")])
    els.append(_overlay("composition_title", 3, [
        _rect("title_band", 1, "50%", "8.5%", "100%", "17%", "#000000"),
        _title(parts, y="8.5%", height="10%"),
    ]))
    els.append(_overlay("place_card", 4, [
        _rect("place_card_bg", 1, "50%", "75%", "88%", "15.5%", "#ffffff", radius="2.4 vmin"),
        _rect("place_card_accent", 2, "8.6%", "75%", "1.1%", "10.5%", "#f76707", radius="0.6 vmin"),
        _label("place_name", 3, "가게 이름", "11.5%", "70.8%", "78%", "5%", "5.4 vmin", "#111111",
               align="0%", anchor_x="0%"),
        _label("place_location", 3, " ", "11.5%", "75.4%", "78%", "4%", "3.9 vmin", "#555555",
               weight="500", align="0%", anchor_x="0%"),
        _label("place_price", 3, " ", "11.5%", "79.4%", "78%", "4%", "4.1 vmin", "#e8590c",
               align="0%", anchor_x="0%"),
    ]))
    return _root(parts, els)


def _build_news(env: str, n: int) -> dict:
    """뉴스형 — 밝은 바탕, 빨간 라벨 + 남색 헤드라인 띠 + 사진 + 남색 상자 자막.

    바탕은 밝지만 제목·자막은 남색 위에 있어서 유저가 고른 글자 색이 그대로 보인다.
      라벨 5.5% · 헤드라인 띠 10~25% · 사진 27~58% · 자막 상자 67%
    """
    box = {"x": "50%", "y": "42.5%", "width": "92%", "height": "31%"}
    parts, els = _scenes(env, n, "#f1f3f5", lambda i, suf, p: _media(i, p, box) + [
        _subtitle(p, suf, i, y="67%", width="86%", background_color="rgba(20,33,61,0.95)",
                  background_x_padding="7%", background_y_padding="18%",
                  background_border_radius="12%")])
    els.append(_overlay("composition_title", 3, [
        _rect("news_label_bg", 1, "17%", "5.6%", "25%", "3.4%", "#e03131", radius="0.8 vmin"),
        _label("news_label", 2, "핵심 요약", "17%", "5.6%", "25%", "3.4%", "3.4 vmin", "#ffffff"),
        _rect("news_band", 1, "50%", "17.5%", "100%", "15%", "#14213d"),
        _title(parts, y="17.5%", width="90%", height="11%"),
        _rect("news_rule", 1, "50%", "60.3%", "92%", "0.35%", "#ced4da"),
    ]))
    return _root(parts, els)


def _build_fullscreen(env: str, n: int) -> dict:
    """풀스크린형 — 사진이 화면 전체 (fit=cover 는 extra_modifications 에서).

    글자가 사진 위에 바로 얹히므로 위·아래에 반투명 어두운 띠를 깐다. 아래 띠는 장면 안에
    둔다 — 맨 위 층에 두면 자막(장면 안)이 띠 아래로 깔려 어두워진다.
      제목 11% · 자막 72%
    """
    box = {"x": "50%", "y": "50%", "width": "100%", "height": "100%"}
    parts, els = _scenes(env, n, "#000000", lambda i, suf, p: _media(i, p, box, fit="cover") + [
        _rect(f"shade{i}", 5, "50%", "73%", "100%", "26%", "rgba(0,0,0,0.42)"),
        _subtitle(p, suf, i, y="72%")])
    els.append(_overlay("composition_title", 3, [
        _rect("top_shade", 1, "50%", "11%", "100%", "22%", "rgba(0,0,0,0.42)"),
        _title(parts, y="11%", height="12%", stroke_color="#000000", stroke_width="1.2 vmin"),
    ]))
    return _root(parts, els)


_HEART = ("M 50 88 C 20 65 4 48 4 30 C 4 15 16 5 29 5 C 39 5 46 11 50 18 "
          "C 54 11 61 5 71 5 C 84 5 96 15 96 30 C 96 48 80 65 50 88 Z")
_BUBBLE = ("M 50 8 C 26 8 8 24 8 45 C 8 56 13 66 21 73 L 16 92 L 37 80 "
           "C 41 81 46 82 50 82 C 74 82 92 66 92 45 C 92 24 74 8 50 8 Z")
_SEND = "M 6 44 L 94 8 L 58 94 L 46 56 Z"
_BOOKMARK = "M 22 6 L 78 6 L 78 94 L 50 70 L 22 94 Z"


def _build_sns_feed(env: str, n: int) -> dict:
    """SNS 피드형 — 어두운 인스타 게시물 모양 (다크 모드라 유저 글자 색이 그대로 보인다).

      프로필 9% · 사진 12~59% · 아이콘 63% · 좋아요 67% · 제목(캡션) 71.5% · 자막 78.5%
    프로필 이름은 @아이디 (extra_modifications).
    """
    box = {"x": "50%", "y": "35.5%", "width": "100%", "height": "47%"}
    parts, els = _scenes(env, n, "#000000", lambda i, suf, p: _media(i, p, box) + [
        _subtitle(p, suf, i, y="78.5%", width="88%")])
    els.append(_overlay("composition_title", 3, [
        _rect("profile_ring", 1, "8.5%", "9%", "8.4 vmin", "8.4 vmin", "#e1306c", radius="4.2 vmin"),
        _rect("profile_dot", 2, "8.5%", "9%", "6.6 vmin", "6.6 vmin", "#f8a5c2", radius="3.3 vmin"),
        _label("profile_name", 3, "@my_blog", "15.5%", "9%", "60%", "4%", "4 vmin", "#ffffff",
               align="0%", anchor_x="0%"),
        _label("profile_more", 3, "···", "92%", "9%", "8%", "4%", "4.6 vmin", "#ffffff"),
        _icon("icon_heart", 3, "8%", "63%", "6.4 vmin", _HEART, stroke="#ff4d6d", fill="#ff4d6d"),
        _icon("icon_comment", 3, "18%", "63%", "6.2 vmin", _BUBBLE),
        _icon("icon_send", 3, "28%", "63%", "6 vmin", _SEND),
        _icon("icon_bookmark", 3, "92%", "63%", "5.8 vmin", _BOOKMARK),
        _label("feed_likes", 3, "좋아요 128개", "5%", "67%", "50%", "3.6%", "3.6 vmin", "#ffffff",
               align="0%", anchor_x="0%"),
        _title(parts, x="5%", x_anchor="0%", x_alignment="0%", y="71.5%", width="90%", height="5.5%",
               font_size_maximum="6.5 vmin"),
    ]))
    return _root(parts, els)


_BUILDERS = {
    "blur_fill": _build_blur_fill,
    "hook": _build_hook,
    "info_card": _build_info_card,
    "news": _build_news,
    "fullscreen": _build_fullscreen,
    "sns_feed": _build_sns_feed,
}
