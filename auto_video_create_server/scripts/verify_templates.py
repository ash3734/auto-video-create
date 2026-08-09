#!/usr/bin/env python3
"""Creatomate 템플릿 10개 실물 검증 — 2026-08-09.

## 왜 필요한가

`scene_counts.py` 의 템플릿 ID 는 코드에 적힌 문자열일 뿐, 그 템플릿이 Creatomate 에
실제로 존재하는지 코드는 모른다. 2026-08-08 에 test 5장면 템플릿(`eda9d421`)이
Creatomate 에서 삭제됐는데 **나흘간 아무도 몰랐다.** 유저가 영상을 만들려다
"렌더링 ID가 없습니다" 를 보고 제보해서야 알았다.

이 스크립트는 그걸 유저보다 먼저 잡는다. 두 가지를 확인한다.

1. **존재 여부** — 10개 ID 를 실제로 GET 해본다 (404 면 즉시 드러남)
2. **엔딩 페이드 적용 여부** — 살아있는 템플릿의 JSON 을 받아
   `add_outro_fade.verify()` 로 검사한다. 10개 중 하나만 빠져도 잡힌다.

## 사용

    export CREATOMATE_API_KEY=...
    python3 scripts/verify_templates.py

    python3 scripts/verify_templates.py --skip-fade   # 존재 여부만

전부 정상이면 종료 코드 0, 하나라도 문제면 1 — CI 나 정기 실행에 그대로 물릴 수 있다.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts.add_outro_fade import verify as verify_fade  # noqa: E402
from services.scene_counts import ALLOWED_SCENE_COUNTS, SCENE_COUNT_CONFIG  # noqa: E402

API_URL = "https://api.creatomate.com/v1/templates/{}"
TIMEOUT = 15


def fetch_template(template_id, api_key):
    """(상태, 페이로드) 반환. 상태: 'ok' | 'not_found' | 'error:...'"""
    req = urllib.request.Request(
        API_URL.format(template_id),
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return "ok", json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "not_found", None
        if e.code in (401, 403):
            # 키 문제 — 여기서 멈추지 않으면 10번 똑같이 실패한다.
            return f"auth_error({e.code})", None
        return f"http_{e.code}", None
    except Exception as e:  # 네트워크 등
        return f"error:{type(e).__name__}", None


def extract_source(payload):
    """템플릿 JSON 본문을 꺼낸다. 응답 형태가 바뀌어도 최대한 버틴다."""
    if not isinstance(payload, dict):
        return None
    for key in ("source", "template", "json"):
        value = payload.get(key)
        if isinstance(value, dict) and "elements" in value:
            return value
    if "elements" in payload:
        return payload
    return None


def main():
    parser = argparse.ArgumentParser(description="Creatomate 템플릿 실물 검증")
    parser.add_argument("--skip-fade", action="store_true", help="존재 여부만 확인")
    args = parser.parse_args()

    api_key = os.environ.get("CREATOMATE_API_KEY")
    if not api_key:
        print("CREATOMATE_API_KEY 환경변수가 필요합니다.", file=sys.stderr)
        print("  export CREATOMATE_API_KEY=...", file=sys.stderr)
        return 2

    failures = []
    print(f"{'환경':6s} {'장면':>4s}  {'템플릿 ID':38s} {'존재':>8s}  엔딩 페이드")
    print("-" * 86)

    for env in ("prod", "test"):
        for n in ALLOWED_SCENE_COUNTS:
            template_id = SCENE_COUNT_CONFIG[n].get(f"template_id_{env}")
            label = f"{env}/{n}장면"

            if not template_id:
                print(f"{env:6s} {n:>4d}  {'(미등록)':38s} {'—':>8s}")
                failures.append(f"{label}: scene_counts.py 에 ID 없음")
                continue

            status, payload = fetch_template(template_id, api_key)

            if status.startswith("auth_error"):
                print(f"\n인증 실패({status}) — CREATOMATE_API_KEY 를 확인하세요.", file=sys.stderr)
                return 2

            if status != "ok":
                mark = "없음" if status == "not_found" else status
                print(f"{env:6s} {n:>4d}  {template_id:38s} {mark:>8s}")
                failures.append(f"{label}: 템플릿 조회 실패 ({status}) id={template_id}")
                continue

            fade_note = "(건너뜀)"
            if not args.skip_fade:
                source = extract_source(payload)
                if source is None:
                    fade_note = "★본문 파싱 실패"
                    failures.append(f"{label}: 응답에서 템플릿 본문을 찾지 못함")
                else:
                    problems = verify_fade(source)
                    if problems:
                        fade_note = f"★{len(problems)}건"
                        for p in problems:
                            failures.append(f"{label}: {p}")
                    else:
                        fade_note = "OK"

            print(f"{env:6s} {n:>4d}  {template_id:38s} {'있음':>8s}  {fade_note}")

    print()
    if failures:
        print(f"문제 {len(failures)}건:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("10개 템플릿 전부 정상 — 존재 + 엔딩 페이드 적용 확인됨")
    return 0


if __name__ == "__main__":
    sys.exit(main())
