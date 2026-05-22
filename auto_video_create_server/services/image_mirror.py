"""외부 이미지 → S3 미러링.

cycle-2.2 BUG-007 (브런치 이미지 Daum CDN → Creatomate 403) 대응.

Creatomate 같은 외부 영상 합성 서비스가 일부 이미지 호스트 (Daum CDN 등) 의 이미지를
fetch 할 때 403 받는 케이스가 있다. 해당 호스트의 이미지는 BE 가 미리 download 해서
S3 에 미러링한 뒤, Creatomate 에는 S3 URL 을 전달한다.

설계:
- 차단 위험 있는 호스트 패턴(MIRROR_REQUIRED_PATTERNS) 만 미러링
- 그 외는 원본 URL 그대로 (Creatomate 가 정상 fetch 하는 호스트는 미러링 비용 0)
- 캐시: sha256(image_url)[:16].{ext} 키 → 동일 URL 재호출 시 S3 비용 0
- 미러링 실패 시 원본 URL 반환 (fallback)
"""
import hashlib
import os
from typing import Optional

import boto3
import requests


BUCKET = "auto-video-tts-files"
PREFIX = "mirrored-images"

# 차단 위험 있는 호스트 패턴 (cycle-2.2 시점). 신규 패턴 발견 시 여기에 추가.
MIRROR_REQUIRED_PATTERNS = [
    "img1.daumcdn.net",  # 브런치 본문 이미지 (BUG-007)
    "img.daumcdn.net",
    "t1.daumcdn.net",
]


def needs_mirror(url: str) -> bool:
    """미러링이 필요한 외부 호스트인지 판별."""
    if not url:
        return False
    return any(p in url for p in MIRROR_REQUIRED_PATTERNS)


def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="ap-northeast-2",
    )


def _exists_in_s3(s3_key: str) -> bool:
    try:
        _s3_client().head_object(Bucket=BUCKET, Key=s3_key)
        return True
    except Exception:
        return False


def _guess_ext(url: str) -> str:
    """URL 의 확장자 추출 (없거나 모호하면 .jpg)."""
    path = url.split("?")[0].lower()
    for e in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        if path.endswith(e):
            return e
    return ".jpg"


def _content_type_for(ext: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


def _public_url(s3_key: str) -> str:
    return f"https://{BUCKET}.s3.ap-northeast-2.amazonaws.com/{s3_key}"


def mirror_image_to_s3(image_url: str, referer: Optional[str] = None) -> str:
    """외부 이미지를 S3 에 미러링하고 공개 URL 반환.

    캐시 적중 시 즉시 반환. miss 시 다운로드 → 업로드 → URL 반환.
    실패 시 원본 URL 반환 (fallback — 일부 호스트는 Creatomate 가 받을 수도 있음).
    """
    ext = _guess_ext(image_url)
    key_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:16]
    s3_key = f"{PREFIX}/{key_hash}{ext}"

    if _exists_in_s3(s3_key):
        return _public_url(s3_key)

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if referer:
            headers["Referer"] = referer
        resp = requests.get(image_url, headers=headers, timeout=15)
        resp.raise_for_status()
        _s3_client().put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=resp.content,
            ContentType=_content_type_for(ext),
        )
        return _public_url(s3_key)
    except Exception as e:
        print(f"[image_mirror] failed for {image_url[:80]}: {e}")
        return image_url  # fallback — Creatomate 가 직접 시도해보도록


def maybe_mirror(image_url: str, referer: Optional[str] = None) -> str:
    """필요한 호스트만 미러링, 나머지는 원본 URL 그대로 반환."""
    if needs_mirror(image_url):
        return mirror_image_to_s3(image_url, referer=referer)
    return image_url
