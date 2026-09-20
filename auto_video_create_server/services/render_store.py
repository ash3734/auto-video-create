"""렌더 기록 저장소 (2026-09-20).

## 왜 남기는가

지금까지 렌더 결과는 **브라우저 안에만** 있었다. 화면이 완료를 기다리다 실패로
바뀌거나 유저가 창을 닫으면, 완성된 영상을 다시 찾을 방법이 없다. 크레딧은 렌더를
접수하는 순간 차감되므로 **돈은 나가고 영상은 사라진다.**

2026-09-15 에 실제로 일어났다 — Creatomate 의 자막용 음성 인식이 18분 걸렸고
(외부 업체 Gladia 지연, Creatomate 확인), 화면은 5분 만에 실패로 바뀌었지만
영상은 그 뒤 정상 완료됐다.

그래서 접수할 때 한 줄 남기고, 웹훅이 오면 결과로 갱신한다. 조회는 두 갈래다.
  · 렌더 ID 로 한 건  — 화면이 완료를 확인할 때
  · 유저별 최근 목록  — "내가 만든 영상" 화면(예정)

## 키 구조

    renders/by-id/{render_id}.json     기록 본체
    renders/by-user/{user_id}.json     그 유저의 최근 렌더 ID 목록 (최신 우선, 최대 100)

저장에 실패해도 영상 생성은 계속돼야 한다. 기록은 부가 기능이고, 여기서 예외를
올리면 이미 크레딧이 빠진 렌더가 에러로 끝난다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from utils.s3_utils import s3_client

KST = timezone(timedelta(hours=9))

BUCKET = "blog-to-short-form-credits"   # 이미 쓰는 버킷을 재사용한다
PREFIX = "renders"
MAX_PER_USER = 100


def _key(render_id: str) -> str:
    return f"{PREFIX}/by-id/{render_id}.json"


def _user_key(user_id: str) -> str:
    return f"{PREFIX}/by-user/{user_id}.json"


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _read(key: str):
    try:
        body = s3_client().get_object(Bucket=BUCKET, Key=key)["Body"].read()
        return json.loads(body)
    except Exception:
        return None


def _write(key: str, data) -> None:
    s3_client().put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def save_submitted(render_id: str, user_id: str, **info) -> bool:
    """렌더를 접수한 직후 한 줄 남긴다. 실패해도 True/False 만 돌려주고 삼킨다."""
    try:
        record = {
            "render_id": render_id,
            "user_id": user_id,
            "status": "planned",
            "url": None,
            "submitted_at": _now(),
            "updated_at": _now(),
        }
        record.update({k: v for k, v in info.items() if v is not None})
        _write(_key(render_id), record)

        ids = _read(_user_key(user_id)) or []
        if not isinstance(ids, list):
            ids = []
        ids = [render_id] + [x for x in ids if x != render_id]
        _write(_user_key(user_id), ids[:MAX_PER_USER])
        return True
    except Exception as e:
        print(f"[render_store] 접수 기록 실패 (무시): {e}")
        return False


def update_result(render_id: str, status: str, url=None, **info) -> bool:
    """웹훅이나 상태 조회로 확인된 결과를 반영한다."""
    try:
        record = _read(_key(render_id))
        if not record:
            # 접수 기록이 없어도 결과는 남긴다 — 없는 것보다 낫다.
            record = {"render_id": render_id, "submitted_at": None}
        record["status"] = status
        if url:
            record["url"] = url
        record["updated_at"] = _now()
        record.update({k: v for k, v in info.items() if v is not None})
        _write(_key(render_id), record)
        return True
    except Exception as e:
        print(f"[render_store] 결과 기록 실패 (무시): {e}")
        return False


def get(render_id: str):
    return _read(_key(render_id))


def list_for_user(user_id: str, limit: int = 20) -> list:
    """그 유저의 최근 렌더 기록. 목록이 깨져 있어도 빈 목록으로 돌려준다."""
    try:
        ids = _read(_user_key(user_id)) or []
        out = []
        for rid in ids[:limit]:
            rec = _read(_key(rid))
            if rec and rec.get("user_id") in (None, user_id):
                out.append(rec)
        return out
    except Exception as e:
        print(f"[render_store] 목록 조회 실패 (빈 목록): {e}")
        return []
