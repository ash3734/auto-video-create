#!/usr/bin/env python3
"""배치 미리보기 이미지를 만든다 (2026-10-18, 백로그 2-1).

    export CREATOMATE_API_KEY=...
    python3 scripts/render_layout_previews.py              # 전체
    python3 scripts/render_layout_previews.py blur_fill    # 하나만

배치마다 같은 샘플(브런치 카페 일러스트·제목·자막)로 1장면 스틸을 렌더해
공개 버킷 static/layout-previews/{배치}.jpg 에 올린다. 배치를 추가하면 이걸 다시 돌린다.
스틸 한 장에 Creatomate 1크레딧.

## 샘플을 왜 이렇게 만들었나
- 그림은 우리가 gpt-image 로 만든 **가로** 일러스트다 — 남의 사진이 아니라 공개 버킷에
  둬도 되고, 가로라서 "흐린 배경"처럼 위아래를 채우는 배치의 차이가 잘 보인다.
- 스틸은 음성 받아쓰기를 하지 않아 자막이 비어 나온다. 그래서 미리보기에서만 자막을
  고정 문구로 바꿔 끼운다 (실제 영상은 지금처럼 음성에서 자동 생성).
- prod 템플릿으로 렌더한다 — test 템플릿은 워터마크가 찍힌다.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ["ENV"] = "production"

from services import layouts  # noqa: E402
from utils.s3_utils import s3_client  # noqa: E402

PUBLIC_BUCKET = "auto-video-tts-files"
SAMPLE_IMAGE = f"https://{PUBLIC_BUCKET}.s3.ap-northeast-2.amazonaws.com/static/layout-previews/sample-brunch.png"
SAMPLE_TITLE = "가로수길 브런치 카페 후기"
SAMPLE_SUBTITLE = "창가 자리가 정말 예뻐요"
SCENES = 5
SNAPSHOT_AT = 1.0


def preview_key(layout_id: str) -> str:
    return f"static/layout-previews/{layout_id}.jpg"


def _static_subtitles(el: dict) -> None:
    for e in el.get("elements") or []:
        if e.get("transcript_source") == "audio1":
            for k in [k for k in e if k.startswith("transcript_")]:
                e.pop(k)
            e["text"] = SAMPLE_SUBTITLE
        _static_subtitles(e)


def _api(method: str, path: str, key: str, body=None) -> dict:
    cmd = ["curl", "-sS", "-X", method, f"https://api.creatomate.com/v1/{path}", "-H", f"Authorization: Bearer {key}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    d = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    return d[0] if isinstance(d, list) else d


def render(layout_id: str, key: str) -> str:
    src = layouts.get_source(layout_id, SCENES)
    _static_subtitles(src)
    src.update({"output_format": "jpg", "snapshot_time": SNAPSHOT_AT})
    mods = {"title.text": SAMPLE_TITLE, "image1.source": SAMPLE_IMAGE, "image1.fit": "contain",
            "image1.visible": "true", "video1.visible": "false"}
    mods.update(layouts.extra_modifications(layout_id, mods, SCENES))
    rid = _api("POST", "renders", key, {"source": src, "modifications": mods, "render_scale": 0.5})["id"]
    for _ in range(40):
        r = _api("GET", f"renders/{rid}", key)
        if r.get("status") in ("succeeded", "failed"):
            break
        time.sleep(3)
    if r.get("status") != "succeeded":
        raise RuntimeError(f"{layout_id} 렌더 실패: {r.get('error_message')}")
    body = urllib.request.urlopen(urllib.request.Request(r["url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    s3_client().put_object(Bucket=PUBLIC_BUCKET, Key=preview_key(layout_id), Body=body, ContentType="image/jpeg",
                           CacheControl="no-cache")
    return f"https://{PUBLIC_BUCKET}.s3.ap-northeast-2.amazonaws.com/{preview_key(layout_id)}"


def main() -> int:
    key = os.environ.get("CREATOMATE_API_KEY")
    if not key:
        print("CREATOMATE_API_KEY 가 필요합니다.")
        return 2
    targets = sys.argv[1:] or list(layouts.LAYOUTS)
    for lid in targets:
        print(f"{lid}: {render(lid, key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
