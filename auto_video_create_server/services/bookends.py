"""첫 화면 문구(인트로) · 끝 화면(아웃트로) (2026-10-18, 백로그 3-6).

effects.py 처럼 배치와 따로, 렌더 직전에 템플릿 JSON 에 덧붙인다. 기본값은 둘 다
"none" 이라 안 고른 유저의 결과물은 한 글자도 바뀌지 않는다.

## 첫 화면 문구 (intro)
첫 장면 처음 1.6초 동안 큰 문구를 얹는다. **장면을 새로 끼워 넣지 않는다** — 나레이션
시작이 늦어지면 쇼츠는 첫 1~2초에 넘겨진다. 첫 프레임이 썸네일처럼 보이게 하는 게 목적.
  none    없음
  title   영상 제목을 크게
  custom  직접 입력

## 끝 화면 (outro)
마지막 장면 뒤에 2.5초짜리 끝 화면을 붙인다. 배경은 마지막 장면 사진을 흐리게 깔고
(영상 장면이면 어두운 바탕), 가운데 문구 하나. 나레이션은 없고 배경음악만 이어진다.
  none     없음
  comment  댓글 유도
  follow   구독·좋아요 유도
  blog     블로그 방문 유도
  custom   직접 입력

영상이 2.5초 길어지므로 Creatomate 렌더 비용도 그만큼(약 10~15%) 는다.

## 글꼴은 제목을 따른다
유저가 자막 스타일에서 고른 제목 글꼴·색(title.font_family / title.fill_color)을
그대로 쓴다. 따로 고르게 하면 설정이 하나 더 늘고, 제목과 끝 화면이 따로 놀게 된다.
"""
from __future__ import annotations

import copy
import re

INTROS = {
    "none": {"name": "없음", "description": "첫 화면에 따로 문구를 넣지 않아요"},
    "title": {"name": "제목 크게", "description": "영상 제목을 첫 화면에 크게 띄워요"},
    "custom": {"name": "직접 입력", "description": "원하는 문구를 첫 화면에 띄워요"},
}
OUTROS = {
    "none": {"name": "없음", "description": "마지막 장면에서 바로 끝나요", "text": ""},
    "comment": {"name": "댓글 유도", "description": "댓글을 남기도록 권해요",
                "text": "여러분 생각은?\n댓글로 알려주세요"},
    "follow": {"name": "구독·좋아요", "description": "구독과 좋아요를 권해요",
               "text": "도움이 됐다면\n구독·좋아요!"},
    "blog": {"name": "블로그 방문", "description": "블로그 원문으로 안내해요",
             "text": "자세한 이야기는\n블로그에서"},
    "custom": {"name": "직접 입력", "description": "원하는 문구로 마무리해요", "text": ""},
}
DEFAULT_INTRO = "none"
DEFAULT_OUTRO = "none"

MAX_TEXT = 40              # 세로 화면에 큰 글씨 두세 줄이 들어가는 정도
# 기본 문구는 한 줄 9자 안쪽으로 둔다 — 넘으면 한 줄이 둘로 접혀 세 줄이 된다
# (2026-10-18 샘플: "여러분 생각은 어떠세요?" 가 세 줄로 접혔다)
INTRO_SECONDS = 1.6
OUTRO_SECONDS = 2.5

_SCENE = re.compile(r"^composition_(\d+)$")
_FALLBACK_FONT = "CookieRun"
_FALLBACK_COLOR = "#fff100"


def normalize_intro(raw) -> str:
    return raw if isinstance(raw, str) and raw in INTROS else DEFAULT_INTRO


def normalize_outro(raw) -> str:
    return raw if isinstance(raw, str) and raw in OUTROS else DEFAULT_OUTRO


def clean_text(raw) -> str:
    """유저 입력 문구 정리 — 줄바꿈은 두 줄까지, 길이는 MAX_TEXT 까지."""
    if not isinstance(raw, str):
        return ""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw.replace("\r", "").split("\n")]
    lines = [ln for ln in lines if ln][:2]
    return "\n".join(lines)[:MAX_TEXT].strip()


def _intro_text(intro, custom, variables) -> str:
    if intro == "title":
        return clean_text(variables.get("title.text"))
    if intro == "custom":
        return clean_text(custom)
    return ""


def _outro_text(outro, custom) -> str:
    if outro == "custom":
        return clean_text(custom)
    return OUTROS[outro]["text"]


def _font(variables):
    return (variables.get("title.font_family") or _FALLBACK_FONT,
            variables.get("title.fill_color") or _FALLBACK_COLOR)


def _is_end_fade(a) -> bool:
    return a.get("time") == "end" and a.get("type") == "fade" and a.get("reversed")


def apply(source: dict, intro=None, intro_text=None, outro=None, outro_text=None, variables=None) -> dict:
    """첫 화면 문구·끝 화면을 덧붙인 사본. 고른 게 없으면 원본 그대로의 사본."""
    intro, outro = normalize_intro(intro), normalize_outro(outro)
    src = copy.deepcopy(source)
    variables = variables or {}
    font, color = _font(variables)

    scenes = [e for e in src.get("elements") or [] if _SCENE.match(e.get("name") or "")]
    if not scenes:
        return src

    text = _intro_text(intro, intro_text, variables)
    if text:
        # 맨 위 트랙에 둔다 — 제목·워터마크보다 위. 첫 장면 위에 얹을 뿐 시간을 밀지 않는다.
        top = max((e.get("track") or 1) for e in src["elements"]) + 1
        src["elements"].append({
            "name": "intro_text", "type": "text", "track": top, "time": 0, "duration": INTRO_SECONDS,
            "text": text, "x": "50%", "y": "50%", "width": "86%", "height": "30%",
            "x_alignment": "50%", "y_alignment": "50%",
            "font_family": font, "font_weight": "700", "font_size_maximum": "13 vmin",
            "fill_color": color, "stroke_color": "#000000", "stroke_width": "1.4 vmin",
            "background_color": "rgba(0,0,0,0.55)", "background_x_padding": "8%",
            "background_y_padding": "10%", "background_border_radius": "6%",
            "animations": [{"type": "fade", "time": "end", "duration": 0.3, "reversed": True}],
        })

    text = _outro_text(outro, outro_text)
    if text:
        last = scenes[-1]
        n = int(_SCENE.match(last["name"]).group(1))
        # 마지막 장면의 끝 페이드는 끝 화면으로 옮긴다 — 남겨두면 끝 화면 직전에 한 번 어두워진다.
        last["animations"] = [a for a in last.get("animations") or [] if not _is_end_fade(a)]
        if not last["animations"]:
            del last["animations"]

        photo = variables.get(f"image{n}.source")
        photo_shown = str(variables.get(f"image{n}.visible", "")).lower() == "true"
        children = []
        if photo and photo_shown:
            children.append({"name": "outro_bg", "type": "image", "track": 1, "time": 0,
                             "source": photo, "fit": "cover", "width": "100%", "height": "100%",
                             "blur_radius": 30, "color_overlay": "rgba(0,0,0,0.55)"})
        children.append({
            "name": "outro_text", "type": "text", "track": 2, "time": 0,
            "text": text, "x": "50%", "y": "52%", "width": "90%", "height": "34%",
            "x_alignment": "50%", "y_alignment": "50%",
            "font_family": font, "font_weight": "700", "font_size_maximum": "10 vmin",
            "fill_color": "#ffffff", "stroke_color": "#000000", "stroke_width": "1.2 vmin",
            "animations": [{"type": "scale", "time": "start", "duration": 0.35, "start_scale": "85%",
                            "end_scale": "100%", "easing": "quadratic-out"}],
        })
        outro_comp = {
            "name": "composition_outro", "type": "composition", "track": last.get("track", 2),
            "duration": OUTRO_SECONDS, "fill_color": "#111111", "elements": children,
            "animations": [{"time": "end", "type": "fade", "duration": 0.3, "reversed": True}],
        }
        # 장면들과 같은 트랙, 마지막 장면 바로 뒤 — time 을 비워 두면 Creatomate 가 이어 붙인다.
        idx = src["elements"].index(last)
        src["elements"].insert(idx + 1, outro_comp)
    return src
