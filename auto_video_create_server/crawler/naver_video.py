"""네이버 블로그 본문 영상 → mp4 주소 (2026-10-20).

## 왜 따로 있나
네이버 에디터(SE)는 본문 영상을 `<video>` 태그로 넣지 않는다. 빈 `se-module-video` 칸과
그 옆 `<script class="__se_module_data" data-module-v2='{"type":"v2_video", ... "vid", "inkey"}'>`
만 있고, 페이지의 스크립트가 재생 정보 API(PLAY_API)를 불러 플레이어를 그린다.
naver.py 는 `<video>` 태그만 찾았기 때문에 영상이 한 번도 잡히지 않았다
(2026-10-20 확인: prod 14일간 글 추출 186번, 영상 0개). 그래서 "영상은 추천을 안 해준다".

## 주소가 만료된다
API 가 주는 mp4 주소에는 서명(`_lsu_sa_` 또는 `__gda__`)이 붙고, 재생 정보 자체에 만료
시각(30분 뒤)이 있다. 유저가 선택 화면에 오래 머물면 영상을 만들 때 주소가 죽어 있을 수 있다.
그래서 주소 끝에 inkey 를 붙여(KEY_PARAM) 돌려주고, 영상을 만들 때 refresh() 로 새 주소를
다시 받는다. 네이버 CDN 은 모르는 쿼리를 무시한다(2026-10-20 확인). inkey 는 글 HTML 에
그대로 공개된 값이다.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import Comment

PLAY_API = "https://apis.naver.com/rmcnmv/rmcnmv/vod/play/v2.0/{vid}"
# 국내에서 받으면 pstatic.net, AWS(Lambda)에서 받으면 akamaized.net 주소가 온다 (2026-10-20 확인).
# akamaized 쪽은 주소에 만료 시각(__gda__=유닉스초_서명, 약 30분 뒤)이 박혀 있다.
VOD_HOST_SUFFIXES = ("naver-vod.pstatic.net", "naver-vod.akamaized.net")
KEY_PARAM = "avc_inkey"
MAX_VIDEOS = 8            # 글 하나에서 가져올 영상 수 (API 호출 수 = 이 값)
TIMEOUT_SECONDS = 5
# 쇼츠는 세로 720×1280 이고 영상은 화면 일부에만 들어간다. 1080p 는 받는 데만 오래 걸린다.
PREFERRED_HEIGHT = 720

_VID_IN_PATH = re.compile(r"/([0-9A-F]{36})/")


def find_modules(main_area) -> List[dict]:
    """본문에서 영상 칸 정보. [{"vid","inkey","title","thumbnail","context"}, ...] (본문 순서)."""
    out = []
    seen = set()
    for tag in main_area.find_all("script", class_="__se_module_data"):
        raw = tag.get("data-module-v2") or tag.get("data-module") or ""
        if "v2_video" not in raw:
            continue
        try:
            mod = json.loads(raw)
        except Exception:
            continue
        data = mod.get("data") or {}
        vid, inkey = data.get("vid"), data.get("inkey")
        if mod.get("type") != "v2_video" or not vid or not inkey or vid in seen:
            continue
        seen.add(vid)
        meta = data.get("mediaMeta") or {}
        out.append({
            "vid": vid,
            "inkey": inkey,
            "title": str(meta.get("title") or "").strip()[:60],
            "thumbnail": data.get("thumbnail") or "",
            "context": _context_after(tag),
        })
        if len(out) >= MAX_VIDEOS:
            break
    return out


def _context_after(tag, limit: int = 80) -> str:
    """영상 바로 뒤 본문 글 — 사진과 같은 방식(naver._extract_caption_and_context)."""
    try:
        parts, total = [], 0
        for s in tag.find_all_next(string=True):
            if isinstance(s, Comment) or (s.parent is not None and s.parent.name == "script"):
                continue
            t = s.strip()
            if not t:
                continue
            parts.append(t)
            total += len(t)
            if total >= limit:
                break
        return " ".join(parts)[:limit]
    except Exception:
        return ""


def _pick_source(play: dict) -> Optional[str]:
    """화질 목록에서 PREFERRED_HEIGHT 이하 중 가장 큰 것. 없으면 가장 작은 것."""
    rows = []
    for v in ((play.get("videos") or {}).get("list") or []):
        src = v.get("source")
        h = (v.get("encodingOption") or {}).get("height") or 0
        if src:
            rows.append((int(h), src))
    if not rows:
        return None
    under = [r for r in rows if r[0] <= PREFERRED_HEIGHT]
    return max(under)[1] if under else min(rows)[1]


def resolve(vid: str, inkey: str) -> Optional[str]:
    """재생 정보 API → mp4 주소 (끝에 KEY_PARAM 을 붙인다). 실패하면 None."""
    try:
        r = requests.get(PLAY_API.format(vid=vid), params={"key": inkey}, timeout=TIMEOUT_SECONDS)
        r.raise_for_status()
        src = _pick_source(r.json())
    except Exception as e:
        print(f"[naver_video] 재생 정보 실패 vid={vid[:8]}: {e}")
        return None
    return _with_key(src, inkey) if src else None


def resolve_all(modules: List[dict]) -> List[dict]:
    """영상 칸마다 resolve — 동시에. 주소를 못 받은 영상은 빠진다. 원소에 "url" 을 채워 돌려준다."""
    if not modules:
        return []
    with ThreadPoolExecutor(max_workers=min(len(modules), MAX_VIDEOS)) as pool:
        urls = list(pool.map(lambda m: resolve(m["vid"], m["inkey"]), modules))
    return [dict(m, url=u) for m, u in zip(modules, urls) if u]


def _with_key(url: str, inkey: str) -> str:
    p = urlparse(url)
    q = parse_qs(p.query, keep_blank_values=True)
    q[KEY_PARAM] = [inkey]
    return urlunparse(p._replace(query=urlencode(q, doseq=True)))


def is_naver_video(url) -> bool:
    try:
        return isinstance(url, str) and urlparse(url).netloc.endswith(VOD_HOST_SUFFIXES)
    except Exception:
        return False


def refresh(url: str) -> str:
    """영상 만들 때 새 주소로. 네이버 영상이 아니거나 새로 못 받으면 받은 주소 그대로."""
    if not is_naver_video(url):
        return url
    p = urlparse(url)
    inkey = (parse_qs(p.query).get(KEY_PARAM) or [None])[0]
    m = _VID_IN_PATH.search(p.path)
    if not inkey or not m:
        return url
    fresh = resolve(m.group(1), inkey)
    return fresh or url
