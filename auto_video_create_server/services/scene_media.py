"""장면별 사진 슬롯의 Creatomate 변수 (2026-09-15).

## 왜 fit 을 지정하는가

템플릿의 사진 틀은 720×640(화면 위쪽 절반, 거의 정사각형)이고, 템플릿에 fit 이
없어서 Creatomate 기본값 `cover`(꽉 채우고 넘치는 부분을 자름)로 렌더됐다.
블로그 사진은 휴대폰 세로 사진(3:4)이 대부분이라 **위아래 3분의 1이 잘렸고**,
휴대폰 캡처는 절반 넘게 잘렸다. 유저가 "내용이 짤린다"고 알려왔다.

`contain` 은 사진 전체를 틀 안에 넣고 남는 공간을 비워 둔다. 빈 공간은 장면의
배경색(#333)으로 보인다. 다음 단계로 템플릿에 같은 사진을 흐리게 깐 배경 요소를
넣을 계획이다 — 그 요소가 생기면 여기서 source 를 함께 넣으면 된다.

AI 기본 배경(`default` 타입)은 이 함수를 쓰지 않는다. 화면을 채우도록 생성한
이미지라 잘려도 잃는 내용이 없고, 여백이 생기면 오히려 빈 화면처럼 보인다.
"""
from __future__ import annotations

IMAGE_FIT = "contain"


def image_slot_variables(slot: int, source: str) -> dict:
    """사진 장면 하나의 변수. slot 은 템플릿 요소 번호(1부터)."""
    return {
        f"image{slot}.source": source,
        f"image{slot}.fit": IMAGE_FIT,
        f"image{slot}.visible": "true",
        f"video{slot}.visible": "false",
    }
