"""일일 사용량 리포트 — 전일 유저별 숏폼 생성 집계 (2026-08-17).

## 왜

PO 요청: "유저들이 매일 얼마나 쇼츠만들기를 실행했는지 매일 메일로 받아보고 싶다."

## 두 가지 수를 함께 낸다

- **시도** — CloudWatch 로그의 `generate_video 호출 user_id=...`
- **성공** — S3 크레딧 이력 (`reason=video_generation`)

성공만 세면 실패한 시도가 안 보인다. 유저가 이탈하는 지점이 바로 거기라, 둘의 차이가
가장 중요한 신호다. (2026-08-17 이전에는 차감 버그로 성공 기록 자체가 없었다 —
`create_creatomate_video` 의 202 관련 주석 참고)

## 날짜 처리

리포트는 KST 기준 "전일"을 다룬다. 그런데 S3 키의 타임스탬프는 `datetime.utcnow()` 라
UTC 다. KST 하루는 UTC 로 전날 15:00 ~ 당일 15:00 에 걸치므로, 키 이름으로 후보를
추린 뒤 레코드의 `timestamp` 로 정확히 거른다.
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import boto3

KST = timezone(timedelta(hours=9))

BUCKET_CREDITS = "blog-to-short-form-credits"
CREDITS_PREFIX = "credits/"
VIDEO_REASON = "video_generation"

# api/blog.py 의 진입 로그와 짝이다. 형식을 바꾸면 시도 집계가 조용히 0 이 된다.
ATTEMPT_PATTERN = "generate_video 호출 user_id="
ATTEMPT_RE = re.compile(r"generate_video 호출 user_id=(\S+)")

# credits/{user_id}/{YYYYMMDD}_{HHMMSS}.json
KEY_RE = re.compile(r"^credits/(?P<user>[^/]+)/(?P<stamp>\d{8}_\d{6})\.json$")


def kst_day_bounds(target_date):
    """KST 기준 하루의 시작/끝을 UTC datetime 으로 반환."""
    start_kst = datetime(target_date.year, target_date.month, target_date.day, tzinfo=KST)
    end_kst = start_kst + timedelta(days=1)
    return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)


def _candidate_keys(s3, start_utc, end_utc):
    """키 이름의 UTC 타임스탬프로 1차 필터링 (객체 읽기 전 후보 추림)."""
    # 경계 오차를 흡수하려고 앞뒤 1시간 여유를 둔다 — 정확한 판정은 레코드로 한다.
    lo = (start_utc - timedelta(hours=1)).strftime("%Y%m%d_%H%M%S")
    hi = (end_utc + timedelta(hours=1)).strftime("%Y%m%d_%H%M%S")

    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_CREDITS, Prefix=CREDITS_PREFIX):
        for obj in page.get("Contents", []):
            m = KEY_RE.match(obj["Key"])
            if m and lo <= m.group("stamp") <= hi:
                keys.append(obj["Key"])
    return keys


def count_successes(target_date, s3=None):
    """유저별 성공(크레딧 이력에 남은 영상 생성) 횟수."""
    s3 = s3 or boto3.client("s3")
    start_utc, end_utc = kst_day_bounds(target_date)
    counts = defaultdict(int)

    for key in _candidate_keys(s3, start_utc, end_utc):
        try:
            body = s3.get_object(Bucket=BUCKET_CREDITS, Key=key)["Body"].read()
            rec = json.loads(body)
        except Exception as e:
            # 레코드 하나를 못 읽는다고 리포트를 통째로 날리지 않는다.
            print(f"[daily_report] 레코드 읽기 실패 (무시): {key} {e}")
            continue

        if rec.get("reason") != VIDEO_REASON:
            continue  # 관리자 충전(admin_add) 등은 사용량이 아니다
        ts = rec.get("timestamp")
        if not ts:
            continue
        try:
            when = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)  # utcnow().isoformat() 는 tz 없음
        if start_utc <= when < end_utc:
            counts[rec.get("user_id") or "(unknown)"] += 1

    return dict(counts)


def count_attempts(target_date, log_group, logs=None):
    """유저별 시도 횟수 (CloudWatch 로그)."""
    logs = logs or boto3.client("logs")
    start_utc, end_utc = kst_day_bounds(target_date)
    counts = defaultdict(int)

    kwargs = {
        "logGroupName": log_group,
        "startTime": int(start_utc.timestamp() * 1000),
        "endTime": int(end_utc.timestamp() * 1000),
        "filterPattern": f'"{ATTEMPT_PATTERN}"',
    }
    try:
        while True:
            resp = logs.filter_log_events(**kwargs)
            for ev in resp.get("events", []):
                m = ATTEMPT_RE.search(ev.get("message", ""))
                if m:
                    counts[m.group(1)] += 1
            token = resp.get("nextToken")
            if not token:
                break
            kwargs["nextToken"] = token
    except Exception as e:
        # 로그 조회 실패로 리포트 전체를 잃지 않는다 — 성공 수만이라도 보낸다.
        print(f"[daily_report] 로그 조회 실패 (시도 수 생략): {e}")
        return None

    return dict(counts)


def format_report(target_date, attempts, successes):
    """사람이 읽을 리포트 본문. 0건인 날도 반드시 내용을 만든다.

    메일이 안 오는 게 "아무도 안 썼다"인지 "리포트가 고장났다"인지 구분되지 않으면
    안 되므로, 실행이 없어도 그 사실을 명시해서 보낸다 (PO 요청).
    """
    lines = [f"[일일 사용량] {target_date.isoformat()} (KST)", ""]

    users = sorted(set(list((attempts or {}).keys()) + list(successes.keys())))
    total_attempts = sum((attempts or {}).values()) if attempts is not None else None
    total_success = sum(successes.values())

    if attempts is None:
        lines.append(f"총 성공 {total_success}회 (시도 수는 로그 조회 실패로 생략)")
    else:
        lines.append(f"총 시도 {total_attempts}회 / 성공 {total_success}회 "
                     f"/ 실패 {total_attempts - total_success}회")
    lines.append("")

    if not users:
        lines.append("실행한 유저가 없습니다.")
    else:
        for uid in users:
            a = (attempts or {}).get(uid)
            s = successes.get(uid, 0)
            if a is None:
                lines.append(f"  {uid:16s} 성공 {s}회")
            else:
                failed = a - s
                tail = f" (실패 {failed})" if failed > 0 else ""
                lines.append(f"  {uid:16s} 시도 {a}회 / 성공 {s}회{tail}")

    lines += [
        "",
        "— 성공은 크레딧 이력(S3), 시도는 Lambda 로그 기준입니다.",
        "  차이가 크면 실패가 몰린 것이니 [ALERT] 메일을 함께 확인하세요.",
    ]
    return "\n".join(lines)


def build_daily_report(target_date=None, log_group=None, s3=None, logs=None):
    """전일(KST) 리포트 본문을 만든다."""
    if target_date is None:
        target_date = (datetime.now(KST) - timedelta(days=1)).date()
    log_group = log_group or os.environ.get(
        "REPORT_LOG_GROUP", "/aws/lambda/auto-create-video-prod"
    )

    successes = count_successes(target_date, s3=s3)
    attempts = count_attempts(target_date, log_group, logs=logs)
    return target_date, format_report(target_date, attempts, successes)


def send_daily_report(topic_arn=None, sns=None, **kwargs):
    """리포트를 만들어 SNS 로 발송. 발송한 본문을 반환."""
    topic_arn = topic_arn or os.environ.get("REPORT_TOPIC_ARN")
    target_date, body = build_daily_report(**kwargs)

    if not topic_arn:
        print("[daily_report] REPORT_TOPIC_ARN 미설정 — 발송 생략")
        print(body)
        return body

    sns = sns or boto3.client("sns")
    sns.publish(
        TopicArn=topic_arn,
        Subject=f"[일일 사용량] {target_date.isoformat()}",
        Message=body,
    )
    print(f"[daily_report] 발송 완료 ({target_date})")
    return body
