"""AI 기본 배경 이미지 생성 — lazy 생성 + S3 캐시 + fallback.

cycle-2 신규. ADR-4 (architecture.md) 참조.

- 호출 시점: generate-video 단계에서 슬롯 type='default' 일 때만
- 모델: gpt-image-2 (1024×1536 세로, quality=low) — 약 $0.006/이미지
- 캐시: sha256(script + slot_idx + 모델/크기)[:16] 키로 S3 'ai-backgrounds/' prefix
- Fallback: 호출 실패 시 정적 배경 PNG

## 2026-09-20 — 하얀 화면 버그

`dall-e-3` 가 OpenAI 에서 내려가 모든 호출이 400 으로 실패하고 있었다
("The model 'dall-e-3' does not exist"). 실패하면 fallback 으로 넘어가는데 그게
단색 배경이라, 유저에게는 **AI 배경 자리가 늘 하얀 화면**으로 보였다.
캐시 폴더도 내내 비어 있었다 — 한 장도 만들어진 적이 없다는 뜻이다.

고치면서 두 가지를 같이 바꿨다.

1. **응답 형식.** gpt-image 계열은 url 이 아니라 **b64_json** 으로 준다.
   모델명만 바꿨다면 `resp.data[0].url` 이 None 이라 또 fallback 으로 떨어졌다.
2. **크기.** 영상이 720×1280 세로인데 정사각형(1024×1024)을 만들고 있었다.
   이제 1024×1536 세로로 만든다 — 좌우가 잘려 나가지 않는다.

모델을 gpt-image-2 로 고른 이유: gpt-image-1 은 2026-10-23,
gpt-image-1.5 는 2026-12-01 종료 예정이라 지금 갈아타면 또 깨진다.
"""
import base64
import hashlib
import os
from typing import Optional

from utils.s3_utils import s3_client
from .alerting import alert
import openai
import requests

# 모델을 바꾸면 캐시 키도 바뀌어야 한다 — 예전 모델로 만든 이미지를 계속 쓰면
# 바꾼 의미가 없다. 크기도 같은 이유로 키에 넣는다.
IMAGE_MODEL = "gpt-image-2"
IMAGE_SIZE = "1024x1536"   # 세로. 영상 틀(720×1280)과 방향이 같다.
IMAGE_QUALITY = "low"      # 배경으로 깔리는 그림이라 low 로 충분하다 (약 $0.006)

BUCKET = "auto-video-tts-files"
CACHE_PREFIX = "ai-backgrounds"
FALLBACK_S3_KEY = "static/default-bg.png"
FALLBACK_URL = (
    f"https://{BUCKET}.s3.ap-northeast-2.amazonaws.com/{FALLBACK_S3_KEY}"
)


def _s3_client():
    # 자격증명을 직접 넘기지 않는다 — 이유는 utils.s3_utils.s3_client 참조.
    # (세션 토큰 누락으로 람다에서 모든 쓰기가 InvalidAccessKeyId 로 실패했다)
    return s3_client()


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
    cache_input = f"{script_text or ''}|{slot_idx}|{IMAGE_MODEL}|{IMAGE_SIZE}"
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
            "세로형 배경 이미지. 글자·로고·워터마크 없음. 심플하고 모던한 추상 배경, "
            "부드러운 색감, 가운데는 비워서 자막이 잘 보이게. "
            f"장면 내용: {(script_text or '')[:200]}"
        )
        client = openai.OpenAI(api_key=api_key)
        resp = client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size=IMAGE_SIZE,
            quality=IMAGE_QUALITY,
            n=1,
        )
        item = resp.data[0]
        # gpt-image 계열은 b64_json 으로 온다. url 은 옛 모델(dall-e)의 방식이라
        # 둘 다 받아 둔다 — 없는 쪽을 쓰면 조용히 fallback(하얀 화면)으로 떨어진다.
        b64 = getattr(item, "b64_json", None)
        if b64:
            img_bytes = base64.b64decode(b64)
        else:
            img_url = getattr(item, "url", None)
            if not img_url:
                raise RuntimeError("이미지 응답에 b64_json·url 이 모두 없음")
            img_bytes = requests.get(img_url, timeout=20).content
        _upload_png_to_s3(s3_key, img_bytes)
        return _public_url(s3_key)
    except Exception as e:
        # 조용히 넘어가면 안 된다 — dall-e-3 가 내려간 뒤 모든 호출이 실패하는데도
        # fallback(단색 배경)만 나가서, 몇 주 동안 아무도 모르고 하얀 화면이 나갔다.
        alert("ai_background", f"AI 배경 생성 실패 — 단색 배경으로 대체: {e}",
              model=IMAGE_MODEL, slot=slot_idx)
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
