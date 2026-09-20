"""Creatomate 웹훅 주소와 검증 (2026-09-20).

Creatomate 는 렌더가 끝나면 우리가 알려준 주소로 POST 한다(성공·실패 모두).
문서에 **서명이나 비밀 헤더가 없다.** 그래서 두 겹으로 막는다.

1. 주소에 비밀 토큰을 붙이고(`?token=…`), 다른 토큰이면 받지 않는다.
2. 받은 내용을 믿지 않고 **Creatomate 에 다시 조회해서** 상태를 확인한다.
   (누가 주소를 알아내 가짜 완료를 보내도, 실제 렌더 상태만 반영된다)

주소나 토큰이 설정되지 않은 환경에서는 웹훅을 아예 요청하지 않는다. 그러면
기존처럼 화면이 상태를 물어보는 방식으로 동작한다 — 기능이 없어질 뿐 깨지지 않는다.
"""
from __future__ import annotations

import hmac
import os

PATH = "/api/blog/creatomate-webhook"


def _base() -> str:
    return (os.environ.get("WEBHOOK_BASE_URL") or "").rstrip("/")


def _secret() -> str:
    return os.environ.get("WEBHOOK_SECRET") or ""


def webhook_url():
    """Creatomate 에 넘길 콜백 주소. 설정이 없으면 None (웹훅 미사용)."""
    base, secret = _base(), _secret()
    if not base or not secret:
        return None
    return f"{base}{PATH}?token={secret}"


def token_ok(token) -> bool:
    """URL 토큰 확인. 설정이 없으면 아무 요청도 받지 않는다."""
    secret = _secret()
    if not secret or not isinstance(token, str):
        return False
    # 글자를 하나씩 비교하면 응답 시간으로 토큰을 알아낼 수 있다.
    return hmac.compare_digest(token, secret)
