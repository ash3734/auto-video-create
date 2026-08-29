"""Typecast TTS — Supertone 대체 (2026-08-05).

Typecast API 는 Supertone 과 마찬가지로 **동기식**이며 오디오 바이트를 바로 반환하므로
호출부 인터페이스(tts_with_*_multi)를 그대로 유지한다.

API 요약 (https://typecast.ai/docs/ko/api-reference/text-to-speech/text-to-speech):
    POST https://api.typecast.ai/v1/text-to-speech
    헤더: X-API-KEY
    본문: voice_id(tc_/uc_ 접두), text(1~2000자), model(ssfm-v30|ssfm-v21),
          output.audio_format(wav|mp3), output.audio_tempo(0.5~2.0)
    응답: 원본 오디오 바이트 (mp3 요청 시 audio/mpeg)
"""
import os
import time
import unicodedata

import boto3
import requests

from .alerting import alert

TYPECAST_URL = "https://api.typecast.ai/v1/text-to-speech"
DEFAULT_MODEL = "ssfm-v30"
DEFAULT_VOICE_ID = "tc_62e8f21e979b3860fe2f6a24"

# Typecast text 제약: 1~2000자
MAX_TEXT_LENGTH = 2000
# audio_tempo 허용 범위
MIN_TEMPO, MAX_TEMPO = 0.5, 2.0

# Lambda 전체 예산이 30초라 한 호출이 오래 붙잡히면 안 된다. (연결, 응답) 초.
REQUEST_TIMEOUT = (5, 15)
# 일시적 오류(429/5xx)만 1회 재시도 — 예산을 크게 넘기지 않는 선에서.
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_BACKOFF_SEC = 1.0

S3_BUCKET = "auto-video-tts-files"


class TypecastError(Exception):
    """Typecast TTS 실패. 메시지는 사용자에게 노출될 수 있으므로 키를 담지 않는다."""


def upload_to_s3(local_path, bucket, s3_key):
    s3 = boto3.client("s3")
    s3.upload_file(local_path, bucket, s3_key)
    return f"https://{bucket}.s3.amazonaws.com/{s3_key}"


def clean_for_speech(text) -> str:
    """읽을 수 없는 문자를 걷어내고 앞뒤 공백을 정리한다 (2026-08-29).

    ## 왜 strip() 만으로는 부족한가

    prod 에서 유저 auctionrun0643 이 8장면으로 만들 때, 블로그 본문이 모자라
    요약 모델이 7·8번 스크립트를 **제로폭 공백(U+200B) 하나**로 채웠다.

    화면에서는 빈 칸으로 보이고, 아래 검사도 통과한다 —

        "\\u200b".strip() == "\\u200b"    # 파이썬은 제로폭 공백을 공백으로 안 본다

    그래서 그대로 Typecast 로 나가 422 "cannot be synthesized" 로 거절당했고,
    유저는 이유를 알 수 없는 영어 에러를 보며 9번을 재시도했다.

    ## 무엇을 지우나

    유니코드 **Cf(format)** 과 **Cc(control)** 범주를 지운다. 제로폭 공백/조이너,
    BOM, 방향 제어 문자 등 "눈에 안 보이는데 문자열 길이는 차지하는" 것들이
    전부 여기 속한다. 네이버 블로그 본문에는 이런 문자가 흔해서, 문장 중간에
    섞여 들어온 경우에도 지우는 편이 합성 품질에 낫다.

    줄바꿈과 탭은 공백으로 바꿔 살린다 — 문장 구분은 유지해야 한다.
    """
    if not isinstance(text, str):
        return ""
    kept = []
    for ch in text:
        category = unicodedata.category(ch)
        if ch in "\n\r\t":
            kept.append(" ")
        elif category in ("Cf", "Cc"):
            continue  # 보이지 않는 문자 — 읽을 수 없다
        else:
            kept.append(ch)
    return " ".join("".join(kept).split())


def _clamp_tempo(speed):
    try:
        tempo = float(speed)
    except (TypeError, ValueError):
        return 1.0
    return max(MIN_TEMPO, min(MAX_TEMPO, tempo))


def tts_with_typecast(text, output_path, api_key, voice_id=None, speed=1.4,
                      model=DEFAULT_MODEL, language="kor"):
    """텍스트 1건 → mp3 파일. 성공 시 (output_path, None) 반환."""
    if not api_key:
        alert("config", "TYPECAST_API_KEY 미설정")
        raise TypecastError("TYPECAST_API_KEY 가 설정되지 않았습니다.")

    text = clean_for_speech(text)
    if not text:
        # 빈 스크립트는 Typecast 가 422 로 거절한다(최소 1자). 장면↔오디오 인덱스가
        # 어긋나면 영상이 통째로 망가지므로, 조용히 넘기지 않고 명확히 실패시킨다.
        raise TypecastError("스크립트가 비어 있어 음성을 만들 수 없어요. 해당 스크립트를 채워주세요.")
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]

    payload = {
        "voice_id": voice_id or DEFAULT_VOICE_ID,
        "text": text,
        "model": model,
        "language": language,
        "output": {
            "audio_format": "mp3",
            "audio_tempo": _clamp_tempo(speed),
        },
    }
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

    last_error = None
    for attempt in range(2):  # 최초 1회 + 재시도 1회
        try:
            response = requests.post(
                TYPECAST_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException as e:
            last_error = f"Typecast 요청 실패: {e}"
            if attempt == 0:
                time.sleep(RETRY_BACKOFF_SEC)
                continue
            alert("typecast", f"재시도 후에도 요청 실패: {e}")
            raise TypecastError(last_error)

        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return output_path, None

        # 실패 — 본문에서 사유만 뽑아 로그/에러에 남긴다 (키는 절대 남기지 않음)
        detail = ""
        try:
            body = response.json()
            detail = body.get("detail") or body.get("message") or body.get("error_code") or ""
        except Exception:
            detail = (response.text or "")[:200]
        last_error = f"Typecast {response.status_code}: {detail}".strip()
        print(f"[tts_typecast] {last_error}")

        if response.status_code in RETRY_STATUSES and attempt == 0:
            time.sleep(RETRY_BACKOFF_SEC)
            continue

        # 401/402/403 은 키가 틀렸거나 플랜/결제 문제 — 재시도로는 절대 안 풀리고
        # 사람이 Typecast 콘솔에 들어가야 한다. 그래서 API 장애와 분리해서 알린다.
        # (2026-08-05~08 에 이 세 코드로 이틀을 날렸다.)
        source = "config" if response.status_code in (401, 402, 403) else "typecast"
        alert(source, last_error)
        raise TypecastError(last_error)

    alert("typecast", last_error or "Typecast 호출 실패")
    raise TypecastError(last_error or "Typecast 호출 실패")


def tts_with_typecast_multi(scripts, api_key, voice_id=None, speed=1.4,
                            output_dir="/tmp/tts_outputs"):
    """스크립트 N개 → mp3 N개 생성 후 S3 업로드.

    반환: (로컬 경로 리스트, S3 URL 리스트) — 기존 Supertone 함수와 동일 시그니처.
    """
    print(f"tts_with_typecast_multi 호출 (scripts={len(scripts)})")
    os.makedirs(output_dir, exist_ok=True)
    audio_local_paths = []
    audio_urls = []

    # 빈 스크립트를 **먼저 전부** 찾아 알려준다. 한 번에 하나씩 알려주면 유저가
    # 7번을 채우고 다시 눌렀다가 8번에서 또 막힌다 (2026-08-29 실제로 그랬다).
    blanks = [
        idx
        for idx, item in enumerate(scripts, 1)
        if not clean_for_speech(item["script"] if isinstance(item, dict) else item)
    ]
    if blanks:
        positions = ", ".join(f"{i}번" for i in blanks)
        raise TypecastError(
            f"{positions} 스크립트가 비어 있어 음성을 만들 수 없어요."
            " 내용을 채우거나 장면 수를 줄여주세요."
        )

    for idx, item in enumerate(scripts, 1):
        text = item["script"] if isinstance(item, dict) else item
        output_path = os.path.join(output_dir, f"shorts_script_{idx}.mp3")
        local_path, _ = tts_with_typecast(
            text, output_path, api_key, voice_id=voice_id, speed=speed
        )
        audio_local_paths.append(local_path)
        ms = int(time.time() * 1000)
        s3_key = f"shorts_script_{idx}_{ms}.mp3"
        audio_urls.append(upload_to_s3(local_path, S3_BUCKET, s3_key))

    return audio_local_paths, audio_urls
