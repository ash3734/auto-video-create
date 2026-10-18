"""효과음 4개를 Pixabay CDN 에서 받아 비공개 버킷에 올린다 (2026-10-18, 백로그 3-5).

    python3 scripts/upload_sfx.py

음원 목록·출처·라이선스는 services/sfx.py 의 SOUNDS 가 기준이다. 공개 버킷이 아닌
이유는 music.py·upload_music.py 참조 (Pixabay 라이선스는 파일 재배포를 금지한다).
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.sfx import BUCKET, SOUNDS, s3_key  # noqa: E402
from utils.s3_utils import s3_client  # noqa: E402


def main() -> int:
    s3 = s3_client()
    for sid, v in SOUNDS.items():
        if sid == "none":
            continue
        # urllib 기본 User-Agent 는 Pixabay CDN 이 403 으로 막는다.
        req = urllib.request.Request(v["cdn"], headers={"User-Agent": "Mozilla/5.0 (Macintosh) auto-video-create/1.0"})
        body = urllib.request.urlopen(req, timeout=30).read()
        if not body.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
            print(f"{sid}: mp3 가 아님 ({body[:12]!r}) — 중단")
            return 1
        s3.put_object(Bucket=BUCKET, Key=s3_key(sid), Body=body, ContentType="audio/mpeg",
                      Metadata={"title": v["title"], "artist": v["artist"],
                                "source-page": v["source_page"], "license": v["license"]})
        print(f"올림 {s3_key(sid)}  {len(body):,} bytes  {v['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
