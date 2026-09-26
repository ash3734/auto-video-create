"""배경음악 mp3 를 S3 에 올린다 — 일회성이지만 재현 가능하게 남긴다 (2026-09-27).

## 왜 공개 버킷이 아닌가

`auto-video-tts-files` 는 버킷 정책이 `s3:GetObject` 를 `*` 에 열어 둔 **공개 버킷**이다.
거기에 mp3 를 올리면 그 주소가 곧 상시 음원 배포처가 된다. Pixabay Content License 는
상업적 이용과 출처 표기 면제는 허용하지만 **음원 파일 자체를 그대로 재배포하는 것은
금지**한다. 그래서 비공개 버킷(`blog-to-short-form-credits`, render_store 와 같은 버킷)에
두고, 미리듣기와 렌더 모두 **만료되는 presigned URL** 로만 넘긴다.

    python3 scripts/upload_music.py <mp3 들이 있는 폴더>

파일명은 `{concept}-{slug}.mp3` 여야 하고, services/music.py 의 TRACKS 와 1:1로 맞는다.
목록과 다르면 올리지 않고 멈춘다 — 조용히 반쪽만 올라가면 FE 에서 깨진 곡이 보인다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.music import BUCKET, PREFIX, TRACKS, s3_key  # noqa: E402
from utils.s3_utils import s3_client  # noqa: E402


def main(src_dir: str) -> int:
    missing = [t["id"] for t in TRACKS if not os.path.exists(os.path.join(src_dir, t["id"] + ".mp3"))]
    if missing:
        print("다음 파일이 폴더에 없습니다:", ", ".join(missing))
        return 1

    s3 = s3_client()
    for t in TRACKS:
        path = os.path.join(src_dir, t["id"] + ".mp3")
        key = s3_key(t["id"])
        with open(path, "rb") as f:
            s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=f.read(),
                ContentType="audio/mpeg",
                # 출처와 라이선스를 파일 자체에 붙여 둔다. 코드와 S3 가 어긋나도
                # 객체만 보고 어디서 온 곡인지 알 수 있어야 한다.
                Metadata={
                    "title": t["title"],
                    "artist": t["artist"],
                    "source-page": t["source_page"],
                    "license": t["license"],
                },
            )
        print(f"올림 {key}  ({os.path.getsize(path):,} bytes)  {t['title']}")

    print(f"\n완료 — {len(TRACKS)}곡, s3://{BUCKET}/{PREFIX}/ (비공개)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
