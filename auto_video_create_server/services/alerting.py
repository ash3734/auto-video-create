"""장애 알림 마커 — CloudWatch 메트릭 필터가 잡는 단일 진입점 (2026-08-08).

## 왜 별도 마커가 필요한가

기존 로그의 에러 표기가 `[!]`, `[모듈명] 실패`, 예외 트레이스백으로 제각각이었고,
특히 `[!]` 가 **진짜 장애**(Creatomate 호출 실패)와 **정상 비즈니스 결과**(크레딧 부족)를
동시에 표시하고 있었다. 그대로 메트릭 필터를 걸면 오탐이 쏟아지고, 오탐이 쏟아지면
사람이 알림을 무시하게 되어 모니터링이 무력해진다.

그래서 **사람이 개입해야 하는 사건에만** `[ALERT]` 를 붙인다.

## 붙이는 기준

붙인다 (사람이 개입해야 함):
    - 외부 API 실패 — Typecast / Creatomate / LLM 이 죽거나 인증이 깨진 경우
    - 설정 오류 — API 키 미설정, 템플릿 ID 가 실물과 불일치
    - 데이터 정합성 파손 — 크레딧 차감 실패 등 돈과 직결되는 쓰기 실패

안 붙인다 (정상 동작이며 유저가 해결할 수 있음):
    - 크레딧 부족
    - 스크립트가 비어 있음
    - 등록되지 않은 블로그 URL

## 사용

    from .alerting import alert
    alert("creatomate", f"렌더 요청 실패 status={status}", template_id=template_id)

CloudWatch 메트릭 필터 패턴은 `"[ALERT]"` 단순 문자열 매칭이므로,
이 접두사를 바꾸면 알람이 조용히 죽는다. 바꿀 때는 메트릭 필터도 같이 고칠 것.
"""
import os

ALERT_PREFIX = "[ALERT]"

# 시크릿이 컨텍스트로 흘러들어가 로그에 남는 사고를 막는다.
# 키 이름에 아래 조각이 들어가면 값을 마스킹한다.
_SECRET_HINTS = ("key", "token", "secret", "password", "authorization", "credential")


def _mask(key: str, value) -> str:
    if any(hint in key.lower() for hint in _SECRET_HINTS):
        return "***"
    return str(value)


def alert(source: str, message: str, **context) -> str:
    """장애를 CloudWatch 에 기록한다. 기록한 문자열을 반환(테스트용).

    Args:
        source: 장애가 난 외부 시스템/모듈 (예: "creatomate", "typecast", "config")
        message: 사람이 읽을 요약. 시크릿을 담지 말 것.
        **context: 추가 진단 정보. 키 이름이 시크릿처럼 보이면 값이 마스킹된다.
    """
    env = os.environ.get("ENV", "unknown")
    parts = [ALERT_PREFIX, f"env={env}", f"source={source}", message]
    for key, value in context.items():
        parts.append(f"{key}={_mask(key, value)}")
    line = " ".join(str(p) for p in parts if p)
    print(line)
    return line
