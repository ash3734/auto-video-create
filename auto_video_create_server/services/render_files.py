"""완성 영상 보관 — Creatomate 결과물을 우리 S3 로 옮겨 둔다 (2026-10-05, 백로그 4-1).

## 왜 옮기는가

Creatomate 는 렌더 결과를 **최대 30일**만 보관하고 지운다. "내가 만든 영상" 화면이
Creatomate 주소를 그대로 보여주면, 9월 20일에 만든 영상부터 차례로 깨진 화면이 된다.
영상 한 편이 2MB 안팎(16~30초, 720×1280)이라 천 편을 모아도 2GB — 보관 비용은
무시할 만하다.

## 왜 비공개 버킷 + presigned 인가

영상에는 유저의 블로그 사진과 목소리가 들어 있다. 공개 버킷(`auto-video-tts-files`)에
두면 주소만 알면 누구나 받는다. 그래서 render_store 와 같은 비공개 버킷에 두고,
목록을 줄 때마다 **만료되는 주소**를 새로 만든다 (music.py 와 같은 방식).

## 실패해도 아무것도 막지 않는다

옮기기는 부가 기능이다. 웹훅·목록 조회 어디서 실패해도 예외를 올리지 않고 None 을
돌려준다. 못 옮긴 영상은 다음 목록 조회 때 다시 시도된다 (api/blog.py my_renders).
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote

import requests

from utils.s3_utils import s3_client

BUCKET = "blog-to-short-form-credits"   # 비공개. render_store 와 같은 버킷
PREFIX = "renders/files"

# Creatomate 보관 기간. 이보다 오래된 영상은 옮겨 두지 않았다면 이미 사라졌다.
CREATOMATE_RETENTION_DAYS = 30

# 재생·다운로드 주소 수명. 목록 화면을 열어 두고 하나씩 보는 시간은 덮되,
# 주소가 복사돼 돌아다니지는 않을 만큼.
URL_EXPIRES = 3600

# 우리 영상은 2MB 안팎이다. 이보다 크면 뭔가 잘못된 것 — 람다 메모리를 지킨다.
MAX_BYTES = 200 * 1024 * 1024


def video_key(render_id: str) -> str:
    return f"{PREFIX}/{render_id}.mp4"


def mirror(render_id: str, video_url: Optional[str]) -> Optional[dict]:
    """Creatomate 영상을 S3 로 복사한다. 성공하면 기록에 붙일 필드, 실패하면 None."""
    if not render_id or not video_url:
        return None
    try:
        resp = requests.get(video_url, timeout=(5, 20))
        if resp.status_code != 200:
            print(f"[render_files] 원본 응답 {resp.status_code} — 건너뜀 render={render_id}")
            return None
        body = resp.content
        if not body or len(body) > MAX_BYTES:
            print(f"[render_files] 크기 이상 {len(body or b'')} — 건너뜀 render={render_id}")
            return None
        s3_client().put_object(
            Bucket=BUCKET,
            Key=video_key(render_id),
            Body=body,
            ContentType="video/mp4",
        )
        return {"video_key": video_key(render_id), "video_bytes": len(body)}
    except Exception as e:
        print(f"[render_files] 복사 실패 (다음 조회 때 재시도) render={render_id}: {e}")
        return None


_UNSAFE = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def download_name(title: Optional[str], submitted_at: Optional[str]) -> str:
    """다운로드 파일 이름. 제목이 있으면 제목, 없으면 날짜.

    운영체제가 파일 이름에 못 쓰는 글자(/ : * ? 등)는 지운다. 제목은 유저가
    자유롭게 입력하는 값이라 그대로 쓰면 다운로드가 깨질 수 있다.
    """
    name = _UNSAFE.sub(" ", (title or "").strip()).strip(" .")[:60]
    if not name:
        name = "shorts_" + (submitted_at or "")[:10].replace("-", "")
    return f"{name}.mp4"


def presign(key: str, filename: Optional[str] = None) -> Optional[str]:
    """재생용(filename 없음) 또는 다운로드용(filename 있음) 만료 주소."""
    params = {"Bucket": BUCKET, "Key": key}
    if filename:
        # 한글 파일 이름은 filename* (RFC 5987) 로 넘겨야 깨지지 않는다.
        params["ResponseContentDisposition"] = (
            f"attachment; filename=\"shorts.mp4\"; filename*=UTF-8''{quote(filename)}"
        )
    try:
        return s3_client().generate_presigned_url("get_object", Params=params, ExpiresIn=URL_EXPIRES)
    except Exception as e:
        print(f"[render_files] presigned 실패 key={key}: {e}")
        return None
