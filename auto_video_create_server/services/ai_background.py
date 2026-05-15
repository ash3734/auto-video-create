"""AI 기본 배경 이미지 생성 — DALL-E 3 lazy 생성 + S3 캐시 + fallback.

cycle-2 신규. ADR-4 (architecture.md) 참조.

- 호출 시점: generate-video 단계에서 슬롯 type='default' 일 때만
- 모델: DALL-E 3 (1024×1024, standard, n=1) — 약 $0.04/이미지
- 캐시: sha256(script + slot_idx)[:16] 키로 S3 'ai-backgrounds/' prefix
- Fallback: DALL-E 호출 실패 또는 타임아웃 시 정적 그라디언트 PNG (B-1 에서 업로드)
"""
import hashlib
import os
from typing import Optional

import boto3
import openai
import requests

BUCKET = "auto-video-tts-files"
CACHE_PREFIX = "ai-backgrounds"
FALLBACK_S3_KEY = "static/default-bg.png"
FALLBACK_URL = (
    f"https://{BUCKET}.s3.ap-northeast-2.amazonaws.com/{FALLBACK_S3_KEY}"
)


def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="ap-northeast-2",
    )


def _public_url(s3_key: str) -> str:
    return f"https://{BUCKET}.s3.ap-northeast-2.amazonaws.com/{s3_key}"


def _exists_in_s3(s3_key: str) -> bool:
    try:
        _s3_client().head_object(Bucket=BUCKET, Key=s3_key)
        return True
    except Exception:
        return False


def _upload_png_to_s3(s3_key: str, png_bytes: bytes) -> None:
    _s3_client().put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=png_bytes,
        ContentType="image/png",
    )


def generate_background_for_slot(script_text: str, slot_idx: int) -> str:
    """슬롯에 사용할 AI 배경 이미지 URL 을 반환한다.

    캐시 적중 시 즉시 반환. miss 시 DALL-E 3 호출 → S3 캐시 → URL 반환.
    실패 시 fallback PNG URL 반환.
    """
    cache_input = f"{script_text or ''}|{slot_idx}"
    cache_key = hashlib.sha256(cache_input.encode("utf-8")).hexdigest()[:16]
    s3_key = f"{CACHE_PREFIX}/{cache_key}.png"

    # 캐시 적중
    if _exists_in_s3(s3_key):
        return _public_url(s3_key)

    # DALL-E 호출
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 미설정")

        prompt = (
            "심플하고 모던한 배경 이미지, 텍스트 없음, 추상적, 한국적 분위기. "
            f"주제 힌트: {(script_text or '')[:120]}"
        )
        client = openai.OpenAI(api_key=api_key)
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        img_url = resp.data[0].url
        img_bytes = requests.get(img_url, timeout=20).content
        _upload_png_to_s3(s3_key, img_bytes)
        return _public_url(s3_key)
    except Exception as e:
        print(f"[ai_background] DALL-E 실패 — fallback 사용: {e}")
        return FALLBACK_URL


def generate_backgrounds_parallel(
    pairs: list,
    max_workers: int = 5,
    per_call_timeout: Optional[int] = None,
) -> dict:
    """여러 슬롯의 AI 배경을 병렬 생성.

    Args:
        pairs: [(slot_idx, script_text), ...]
        max_workers: 동시 호출 수 (Lambda 15분 한도 / DALL-E 동시 처리량 고려)
        per_call_timeout: 호출당 wait timeout (초). None 이면 무제한.

    Returns: {slot_idx: url, ...}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict = {}
    if not pairs:
        return results

    workers = min(max_workers, max(1, len(pairs)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {
            executor.submit(generate_background_for_slot, script, idx): idx
            for idx, script in pairs
        }
        for future in as_completed(future_to_idx, timeout=per_call_timeout):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                print(f"[ai_background] slot {idx} 실패 — fallback: {e}")
                results[idx] = FALLBACK_URL
    return results
