"""음성 미리듣기 — 유저의 실제 스크립트를 골라둔 음성으로 읽어준다 (2026-08-17).

## 설계

제네릭한 샘플 문장("안녕하세요")이 아니라 **화면에 이미 떠 있는 스크립트**를 읽힌다.
자기 콘텐츠가 그 목소리로 어떻게 들리는지가 진짜 판단 근거이고, 미리 만들어 둘 샘플
파일도 필요 없다. (PO 제안, 2026-08-17)

## 캐시가 핵심이다

미리듣기는 실시간 TTS 호출이라, 캐시가 없으면 ▶ 를 연타할 때마다 비용이 나간다.
`(voice_id, 텍스트)` 해시를 S3 키로 써서 같은 조합이면 재생성하지 않는다.
스크립트를 수정하면 해시가 바뀌어 새로 생성되는데, 이게 맞는 동작이다.

비용 감각: 미리듣기는 **한 줄**이라 영상 한 편(5줄)의 1/5이다. 5개 음성을 다 들어봐도
영상 1편 분량. 지연은 prod 로그 기준 한 줄에 1초 안팎이라 FE 에 로딩 상태가 필요하다.
"""
import hashlib
import os
import tempfile

import boto3
from botocore.exceptions import ClientError

from .tts_typecast import S3_BUCKET, TypecastError, tts_with_typecast, upload_to_s3
from .voices import normalize_voice_id

S3_PREFIX = "voice-previews"

# 영상 생성과 같은 속도로 들려줘야 실제 결과물과 일치한다.
PREVIEW_SPEED = 1.4

# 미리듣기는 한 문장이면 충분하다. 너무 길면 비용과 지연만 늘고 판단에는 도움이 안 된다.
MAX_PREVIEW_CHARS = 200


def _cache_key(voice_id: str, text: str) -> str:
    """(음성, 텍스트) 조합의 S3 키. 텍스트가 한 글자만 달라도 다른 키가 된다."""
    digest = hashlib.sha256(f"{voice_id}\x00{text}".encode("utf-8")).hexdigest()[:20]
    return f"{S3_PREFIX}/{voice_id}/{digest}.mp3"


def _s3():
    return boto3.client("s3")


def _existing_url(key: str) -> str:
    """이미 만들어 둔 미리듣기가 있으면 URL, 없으면 None."""
    try:
        _s3().head_object(Bucket=S3_BUCKET, Key=key)
    except ClientError:
        return None
    except Exception as e:
        # 조회 실패는 캐시 미스로 처리 — 재생성하면 되므로 요청을 실패시키지 않는다.
        print(f"[voice_preview] 캐시 조회 실패 (재생성으로 진행): {e}")
        return None
    return f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"


def get_preview_url(voice_id: str, text: str, api_key: str) -> dict:
    """미리듣기 mp3 URL 반환.

    반환: {"status": "success", "url": ..., "cached": bool}
          {"status": "error", "message": ...}

    텍스트가 비어 있으면 만들 수 없다. 영상 생성 경로와 달리 여기서는 조용히 거절한다
    — 미리듣기 실패가 영상 제작을 막아서는 안 되므로 FE 는 이 실패를 흡수한다.
    """
    text = (text or "").strip()
    if not text:
        return {"status": "error", "message": "들려드릴 문장이 없어요."}
    if len(text) > MAX_PREVIEW_CHARS:
        text = text[:MAX_PREVIEW_CHARS]

    voice_id = normalize_voice_id(voice_id)
    key = _cache_key(voice_id, text)

    cached = _existing_url(key)
    if cached:
        return {"status": "success", "url": cached, "cached": True}

    tmp_path = os.path.join(tempfile.gettempdir(), f"preview_{os.getpid()}.mp3")
    try:
        tts_with_typecast(text, tmp_path, api_key, voice_id=voice_id, speed=PREVIEW_SPEED)
        url = upload_to_s3(tmp_path, S3_BUCKET, key)
    except TypecastError as e:
        # tts_typecast 안에서 이미 [ALERT] 를 남긴다 — 여기서 중복 알림하지 않는다.
        print(f"[voice_preview] TTS 실패: {e}")
        return {"status": "error", "message": "미리듣기를 만들지 못했어요. 다시 시도해주세요."}
    except Exception as e:
        print(f"[voice_preview] 업로드 실패: {e}")
        return {"status": "error", "message": "미리듣기를 만들지 못했어요. 다시 시도해주세요."}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return {"status": "success", "url": url, "cached": False}
