"""화면 배치(레이아웃) — 렌더에 쓸 템플릿 JSON 을 코드에서 고른다 (2026-10-05, 백로그 5-2·2-1).

## 왜 코드로 옮겼나

PO 가 한국 쇼츠에서 흔한 배치를 여러 개 템플릿으로 만들고 싶어 한다. 그런데 Creatomate
템플릿은 장면 수(4~8)마다, prod/test(워터마크 유무)마다 따로라 **배치 하나에 10개**다.
에디터에서 손으로 만들면 배치 7개에 70개가 된다.

Creatomate 는 저장된 템플릿 ID 대신 **템플릿 JSON 자체(source)** 를 렌더 요청에
실어 보내도 똑같이 렌더한다 (2026-10-05 test 5장면으로 확인: 한글 폰트·자동 자막·
modifications 모두 정상). 그래서 배치를 코드로 정의하고, 장면 수별 변형은 코드가 만든다.

## 1단계: 지금 배치(letterbox)는 "그대로 복사"

지금 쓰는 템플릿 10개를 `layout_sources/letterbox/` 에 **그대로** 저장했다
(scripts/snapshot_templates.py). 새로 생성하지 않은 이유: 10개 템플릿이 손으로 고쳐지며
조금씩 어긋나 있다 — 예를 들어 1번 장면만 자막 나눔 방식(`transcript_split`)이 다르다.
코드로 "깨끗하게" 다시 만들면 유저의 영상이 조용히 바뀐다. 복사본이면 바이트 단위로 같다.

## 주의 — 에디터 수정은 더 이상 반영되지 않는다

이제 렌더는 이 파일들을 쓴다. Creatomate 에디터에서 템플릿을 고쳤다면
`python3 scripts/snapshot_templates.py` 로 다시 가져와 배포해야 한다.
`--check` 로 어긋남을 확인할 수 있다.
"""
from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from typing import Optional

SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layout_sources")

DEFAULT_LAYOUT = "letterbox"

# 화면에 노출할 배치 목록. 새 배치는 여기에 추가한다.
LAYOUTS = {
    "letterbox": {
        "name": "기본",
        "description": "위 제목 · 가운데 사진 · 아래 자막",
    },
}


def _env_key() -> str:
    # scene_counts.get_template_id 와 같은 기준 — prod 에 워터마크(test) 템플릿이 나가면 안 된다.
    return "prod" if os.environ.get("ENV") == "production" else "test"


def normalize_layout(raw) -> str:
    """요청값을 허용된 배치로. 모르는 값이면 기본 배치 — 영상 생성을 막을 사안이 아니다."""
    return raw if isinstance(raw, str) and raw in LAYOUTS else DEFAULT_LAYOUT


@lru_cache(maxsize=64)
def _load(layout_id: str, env: str, scene_count: int) -> Optional[dict]:
    path = os.path.join(SOURCES_DIR, layout_id, f"{env}_{scene_count}.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)["source"]
    except (OSError, ValueError, KeyError) as e:
        print(f"[layouts] 템플릿 JSON 을 못 읽음 {path}: {e}")
        return None


def get_source(layout_id, scene_count: int) -> Optional[dict]:
    """렌더에 실어 보낼 템플릿 JSON. 없으면 None (호출하는 쪽이 template_id 로 대신 렌더).

    캐시된 원본을 돌려주면 호출하는 쪽이 고쳤을 때 다음 요청까지 오염되므로 복사본을 준다.
    """
    src = _load(normalize_layout(layout_id), _env_key(), int(scene_count))
    return copy.deepcopy(src) if src is not None else None
