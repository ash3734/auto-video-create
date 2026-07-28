"""
concept_samples.py — sprint-4 신규

컨셉 영상 샘플 4종의 정의. concept_sample_id 를 키로 하는 단일 소스.
- extract-all: scene_count, hook_prompt 사용
- generate-video: creatomate_template_id, subtitle_element_suffixes 사용
- GET /api/blog/concept-samples: name, is_default, scene_count, hero_still_url,
  sample_video_url 만 공개(list_samples_public())

★ 전 필드 placeholder. 실제 값은 PO 자산 확보 후 갱신(architecture.md DEP-S4-01/05/06).

저장 위치는 코드 상수로 확정(PO 2026-07-28, architecture.md §2-1 / data-model.md §1).
S3 JSON 안(B)은 기각됐으나, 향후 전환 니즈 대비 아래 함수(get_sample / list_samples_public /
get_template_id) 시그니처는 저장 위치와 무관하게 재사용 가능하도록 설계돼 있다 — 전환 비용은
이 파일 내부 구현 교체로 한정된다.

★ 릴리즈 게이트(architecture.md §5, 비협상): creatomate_template_id 가 전부 None(placeholder)인
상태로는 prod 배포 금지. 최소 sample_1(기본값)의 실 template_id 확보 전까지 prod 릴리즈 불가.
"""

from typing import Optional, TypedDict


class TemplateIdByEnv(TypedDict):
    test: Optional[str]
    production: Optional[str]


class ConceptSample(TypedDict):
    concept_sample_id: str
    name: str
    is_default: bool
    scene_count: int
    hero_still_url: Optional[str]
    sample_video_url: Optional[str]
    hook_prompt: str
    creatomate_template_id: TemplateIdByEnv
    subtitle_element_suffixes: Optional[list[str]]


DEFAULT_SAMPLE_ID = "sample_1"

SAMPLE_DEFINITIONS: dict[str, ConceptSample] = {
    "sample_1": {
        "concept_sample_id": "sample_1",
        "name": "컨셉 1",
        "is_default": True,
        "scene_count": 4,
        "hero_still_url": None,
        "sample_video_url": None,
        "hook_prompt": (
            # placeholder — 02-insight.md §3-2 "밝은(감탄/텐션형)" 계열 임시 배정.
            # 실제 4종 확정 후 샘플별로 재배정 필요.
            "감탄사·리액션을 결론보다 먼저 배치하는 감탄/텐션형 훅을 1문장, "
            "15자 내외로 작성해줘. 예: '여기 진짜 미쳤어요, 보자마자 감탄함'"
        ),
        "creatomate_template_id": {"test": None, "production": None},
        "subtitle_element_suffixes": None,
    },
    "sample_2": {
        "concept_sample_id": "sample_2",
        "name": "컨셉 2",
        "is_default": False,
        "scene_count": 6,
        "hero_still_url": None,
        "sample_video_url": None,
        "hook_prompt": (
            # placeholder — "차분한(공감/스토리형)" 계열 임시 배정.
            "청자의 상황 공감이나 잔잔한 질문으로 시작하는 공감/스토리형 훅을 1문장, "
            "15자 내외로 작성해줘. 예: '퇴근하고 지친 날, 자꾸 생각나는 곳'"
        ),
        "creatomate_template_id": {"test": None, "production": None},
        "subtitle_element_suffixes": None,
    },
    "sample_3": {
        "concept_sample_id": "sample_3",
        "name": "컨셉 3",
        "is_default": False,
        "scene_count": 5,
        "hero_still_url": None,
        "sample_video_url": None,
        "hook_prompt": (
            # placeholder — "역동적(충격/속도형)" 계열 임시 배정.
            "단언·수치·반전 등으로 시작하는 충격/속도형 훅을 1문장, 15자 내외로 "
            "작성해줘. 과장 표현 없이 사실 기반으로. 예: '웨이팅 2시간. 그래도 갑니다'"
        ),
        "creatomate_template_id": {"test": None, "production": None},
        "subtitle_element_suffixes": None,
    },
    "sample_4": {
        "concept_sample_id": "sample_4",
        "name": "컨셉 4",
        "is_default": False,
        "scene_count": 4,
        "hero_still_url": None,
        "sample_video_url": None,
        "hook_prompt": (
            # placeholder — 4번째 계열 임시(정보형). PO 확정 시 실제 컨셉으로 교체.
            "핵심 정보를 담백하게 제시하며 시작하는 훅을 1문장, 15자 내외로 "
            "작성해줘. 과장 없이 사실 위주로."
        ),
        "creatomate_template_id": {"test": None, "production": None},
        "subtitle_element_suffixes": None,
    },
}


def get_sample(concept_sample_id: Optional[str]) -> ConceptSample:
    """concept_sample_id 로 샘플 조회. 없거나 미인식 값이면 기본 샘플로 폴백."""
    return SAMPLE_DEFINITIONS.get(concept_sample_id) or SAMPLE_DEFINITIONS[DEFAULT_SAMPLE_ID]


def list_samples_public() -> list[dict]:
    """GET /api/blog/concept-samples 응답용 — BE 내부 전용 필드 제외.

    제외 필드(api-contract.md): creatomate_template_id, subtitle_element_suffixes, hook_prompt
    """
    return [
        {
            "concept_sample_id": s["concept_sample_id"],
            "name": s["name"],
            "is_default": s["is_default"],
            "scene_count": s["scene_count"],
            "hero_still_url": s["hero_still_url"],
            "sample_video_url": s["sample_video_url"],
        }
        for s in SAMPLE_DEFINITIONS.values()
    ]


def get_template_id(concept_sample_id: Optional[str], env: Optional[str]) -> Optional[str]:
    """concept_sample_id + ENV → Creatomate template_id. 미확보 시 None."""
    sample = get_sample(concept_sample_id)
    env_key = "production" if (env or "").lower() == "production" else "test"
    return sample["creatomate_template_id"].get(env_key)


def get_scene_count(concept_sample_id: Optional[str]) -> int:
    """concept_sample_id → scene_count(N). extract-all/blog_shorts 에서 사용."""
    return get_sample(concept_sample_id)["scene_count"]
