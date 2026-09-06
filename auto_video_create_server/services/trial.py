"""공개 체험 계정 — prod 차단 + IP 당 일일 횟수 제한 (2026-08-30).

## 배경

랜딩에서 `test` 계정의 아이디·비밀번호를 공개해, 문의 없이 바로 써보게 한다(PO 결정).
test 서버는 워터마크가 찍히므로 결과물을 그대로 가져다 쓰긴 어렵다.

## 왜 prod 차단이 필요한가

`users.json` 은 **버킷 하나를 test 와 prod 가 함께 본다.** 로그인도 ENV 를 구분하지
않고 구독 기간만 본다. 그래서 비밀번호를 공개하면 **prod 서버에도 같은 계정으로
로그인된다** — 워터마크 없는 영상이 나가고 크레딧도 실제로 차감된다.

계정을 지우거나 구독을 끊으면 test 에서도 못 쓰게 되므로, **ENV 로 갈라서 prod 에서만
거부**한다.

## 왜 서버에서 횟수를 세는가

브라우저 세션 기준으로 막으면 시크릿 모드나 저장소 삭제로 바로 뚫린다. 그런데
**Creatomate·Typecast·OpenAI 키를 test 와 prod 가 공유**한다(확인함). 체험 트래픽이
몰리면 그 달 prod 고객이 영상을 못 만든다. 그래서 서버에서 IP 단위로 센다.

IP 는 해시해서 저장한다. 우리가 원본 IP 를 보관할 이유가 없다.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

from .alerting import alert
from utils.s3_utils import s3_client

KST = timezone(timedelta(hours=9))

# 공개된 체험 계정. 이 값이 바뀌면 랜딩 페이지 안내 문구도 함께 바꿔야 한다.
TRIAL_USER_ID = "test"

# IP 하나가 하루에 만들 수 있는 영상 수 (PO 결정).
DAILY_LIMIT_PER_IP = 3

# 하루 총합이 이 값을 넘으면 알린다. 인기인지 남용인지는 사람이 판단한다.
DAILY_TOTAL_ALERT = 10

BUCKET = "blog-to-short-form-credits"   # 이미 쓰고 있는 버킷을 재사용한다
PREFIX = "trial-usage"


def is_prod() -> bool:
    """ENV 가 test 가 아니면 전부 prod 로 본다 (없거나 오타여도 안전한 쪽)."""
    return os.environ.get("ENV", "").lower() != "test"


def is_trial_user(user_id) -> bool:
    return isinstance(user_id, str) and user_id == TRIAL_USER_ID


def blocked_on_prod(user_id) -> bool:
    """공개 계정이 prod 로 들어오려는 상황인가."""
    return is_trial_user(user_id) and is_prod()


def _today() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def _key(day: str) -> str:
    return f"{PREFIX}/{day}.json"


def _hash_ip(ip: str) -> str:
    """원본 IP 는 남기지 않는다. 같은 날 같은 IP 를 알아보기만 하면 된다."""
    salt = _today()  # 날짜를 섞어 날짜별로 값이 달라지게 한다
    return hashlib.sha256(f"{salt}\x00{ip}".encode("utf-8")).hexdigest()[:16]


def client_ip(request) -> str:
    """API Gateway 를 거치므로 X-Forwarded-For 의 **첫 번째** 주소가 원 클라이언트다."""
    xff = ""
    try:
        xff = request.headers.get("x-forwarded-for") or ""
    except Exception:
        pass
    if xff:
        return xff.split(",")[0].strip()
    try:
        return (request.client.host if request.client else "") or "unknown"
    except Exception:
        return "unknown"


def _load(day: str) -> dict:
    try:
        body = s3_client().get_object(Bucket=BUCKET, Key=_key(day))["Body"].read()
        data = json.loads(body)
        return data if isinstance(data, dict) else {}
    except Exception:
        # 없거나 못 읽으면 빈 값으로 시작한다 — 집계 실패가 체험을 막으면 안 된다.
        return {}


def _save(day: str, data: dict) -> None:
    s3_client().put_object(
        Bucket=BUCKET,
        Key=_key(day),
        Body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def check_and_count(ip: str) -> dict:
    """체험 1회를 기록하고 허용 여부를 돌려준다.

    반환: {"allowed": bool, "used": int, "limit": int, "daily_total": int}

    집계에 실패하면 **허용**한다. 카운터가 깨졌다고 체험을 막으면, 고칠 수 있는
    사람(우리)이 아니라 써보러 온 사람이 손해를 본다. 대신 알림은 남긴다.
    """
    day = _today()
    try:
        data = _load(day)
        counts = data.get("counts") or {}
        h = _hash_ip(ip)
        used = int(counts.get(h, 0))

        if used >= DAILY_LIMIT_PER_IP:
            total = sum(int(v) for v in counts.values())
            return {"allowed": False, "used": used,
                    "limit": DAILY_LIMIT_PER_IP, "daily_total": total}

        counts[h] = used + 1
        total = sum(int(v) for v in counts.values())
        alerted = bool(data.get("alerted"))

        # 하루 총합이 기준을 넘는 순간 한 번만 알린다. 매 요청마다 울리면 소음이 된다.
        if total >= DAILY_TOTAL_ALERT and not alerted:
            alert("trial", f"체험 사용이 하루 {DAILY_TOTAL_ALERT}회를 넘었습니다",
                  daily_total=total, unique_ips=len(counts), day=day)
            alerted = True

        _save(day, {"counts": counts, "alerted": alerted})
        return {"allowed": True, "used": used + 1,
                "limit": DAILY_LIMIT_PER_IP, "daily_total": total}
    except Exception as e:
        print(f"[trial] 사용량 집계 실패 (허용으로 진행): {e}")
        return {"allowed": True, "used": 0,
                "limit": DAILY_LIMIT_PER_IP, "daily_total": 0}
