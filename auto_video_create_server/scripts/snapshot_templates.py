#!/usr/bin/env python3
"""Creatomate 템플릿 10개를 코드로 가져온다 / 어긋났는지 확인한다 (2026-10-05, 백로그 5-2).

## 왜

2026-10-05 부터 영상은 Creatomate 에 저장된 템플릿(template_id)이 아니라 **코드에
들어 있는 템플릿 JSON(source)** 으로 렌더한다 (services/layouts.py). 그래야 배치
(레이아웃)를 코드로 늘릴 수 있다 — 배치 하나에 템플릿이 10개(장면 수 4~8 × prod/test)씩
필요해서, 에디터로 손으로 만들면 감당이 안 된다.

**이 말은 곧, Creatomate 에디터에서 템플릿을 고쳐도 영상에 반영되지 않는다는 뜻이다.**
에디터에서 고쳤다면 이 스크립트로 다시 가져와야 한다. `--check` 는 그 어긋남을 잡는다.

## 사용

    export CREATOMATE_API_KEY=...
    python3 scripts/snapshot_templates.py            # 10개를 받아 services/layout_sources/letterbox/ 에 저장
    python3 scripts/snapshot_templates.py --check    # 저장본과 에디터의 템플릿이 같은지만 확인 (다르면 종료 코드 1)
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from services.layouts import SOURCES_DIR  # noqa: E402
from services.scene_counts import SCENE_COUNT_CONFIG  # noqa: E402

LAYOUT_ID = "letterbox"


def _fetch(template_id: str, api_key: str) -> dict:
    # urllib 기본 User-Agent 는 Creatomate 앞단에서 403 이 난다 (verify_templates.py 참조).
    out = subprocess.run(
        ["curl", "-sS", "-f", "-H", f"Authorization: Bearer {api_key}",
         f"https://api.creatomate.com/v1/templates/{template_id}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def _path(env: str, n: int) -> str:
    return os.path.join(SOURCES_DIR, LAYOUT_ID, f"{env}_{n}.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="저장본과 에디터 템플릿 비교만")
    args = ap.parse_args()
    api_key = os.environ.get("CREATOMATE_API_KEY")
    if not api_key:
        print("CREATOMATE_API_KEY 가 필요합니다.")
        return 2

    os.makedirs(os.path.join(SOURCES_DIR, LAYOUT_ID), exist_ok=True)
    drift = []
    for n, cfg in sorted(SCENE_COUNT_CONFIG.items()):
        for env in ("prod", "test"):
            tid = cfg[f"template_id_{env}"]
            live = _fetch(tid, api_key)
            record = {
                "template_id": tid,
                "template_name": live.get("name"),
                "template_updated_at": live.get("updated_at"),
                "source": live["source"],
            }
            path = _path(env, n)
            if args.check:
                try:
                    saved = json.load(open(path, encoding="utf-8"))
                except FileNotFoundError:
                    saved = None
                same = saved is not None and saved.get("source") == live["source"]
                print(f"{'같음 ' if same else '다름!'} {env}_{n}  {live.get('name')}  (에디터 수정 {live.get('updated_at')})")
                if not same:
                    drift.append(f"{env}_{n}")
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(record, f, ensure_ascii=False, indent=1)
                    f.write("\n")
                print(f"저장 {path}  {live.get('name')}")

    if args.check and drift:
        print(f"\n에디터에서 고친 템플릿이 코드에 반영되지 않았습니다: {', '.join(drift)}")
        print("반영하려면: python3 scripts/snapshot_templates.py  (그 뒤 배포)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
