import copy
import os
import anthropic
from dotenv import load_dotenv
import json
import re

load_dotenv()

CLAUDE_MODEL = "claude-sonnet-5"

# 구조화 출력 스키마 — Claude 가 항상 이 형태의 JSON 만 반환하도록 강제
# sprint-4: scripts 배열 길이는 더 이상 고정 5가 아니라 scene_count(N)로 가변.
# build_shorts_output_schema() 가 요청마다 minItems/maxItems 를 주입한다.
SHORTS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "scripts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"script": {"type": "string"}},
                "required": ["script"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "scripts"],
    "additionalProperties": False,
}


def build_shorts_output_schema(scene_count: int) -> dict:
    """SHORTS_OUTPUT_SCHEMA 에 scene_count(N) 기준 minItems/maxItems 를 주입한 스키마 반환.

    architecture.md §3-3 — Claude structured output 경로에서만 개수를 스키마로 강제 가능.
    OpenAI fallback 경로는 구조화 출력을 쓰지 않아 이 스키마가 적용되지 않는다(§3-3 비대칭, 문서화됨).
    """
    schema = copy.deepcopy(SHORTS_OUTPUT_SCHEMA)
    schema["properties"]["scripts"]["minItems"] = scene_count
    schema["properties"]["scripts"]["maxItems"] = scene_count
    return schema


def extract_json_from_codeblock(content):
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
    if match:
        return match.group(1)
    return content

def fix_json_keys(json_str):
    # { key: value } → { "key": value }
    json_str = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)
    return json_str

# cycle-2: 카테고리별 프롬프트 분기 (ADR-3 / architecture.md).
# - restaurant: 기존 맛집 프롬프트 (역/동 + 상호명, 메뉴/가격, 위트)
# - general: 일반 블로그용 generic 프롬프트 (핵심 키워드 + 본문 핵심, 위트 유지)
#
# sprint-4: category(맛집/일반) 축과 concept_sample(scene_count/hook_prompt) 축은 직교
# (architecture.md F-4) — 두 프롬프트 분기가 {scene_count}/{hook_prompt} 로 동시 적용된다.
RESTAURANT_PROMPT = """
아래 블로그 글을 바탕으로, 유튜브 쇼츠 영상에 어울리는 제목과 스크립트를 자동으로 만들어줘.

타이틀 : '무슨무슨역 상호명' 또는 '무슨무슨동 상호명' 형식으로 생성해줘. (예: '교대역 스키당', '압구정동 저스트스테이크')
타이틀은 블로그 본문에서 역/동/상호명을 추출해서 만들어줘. 만약 역/동 정보가 없으면 상호명만 사용해줘.

- 훅(첫 문장) 작성 지침:
{hook_prompt}

- 스크립트 작성 Tip :
첫번째 스크립트는 위 훅 지침을 참고해서 제일 강렬하게 이목을 끌 수 있게 작성해줘.
메뉴에 대한 가격과 설명이 들어가면 좋아
마지막 스크립트는 마무리하는 말투로 작성해줘.
그 사이 스크립트들은 본문 핵심 내용 위주로.

- 주의 사항 :
줄바꿈이 필요한 부분은 반드시 \\n(역슬래시+n)으로 표기해줘. 실제 엔터(줄바꿈)는 사용하지 마.
각 줄은 20자 내외의 자연스러운 한두 문장으로 작성해줘.
설명이나 순서 안내 문구는 넣지 마.
특히, 스크립트의 말투는 너무 딱딱하지 않게! 유튜브 쇼츠에서 재미있게 볼 수 있도록 위트있고 센스 있게 써줘.

- 출력 형식
아래는 예시이고, 반드시 예시와 같이 JSON 객체 형태로 반환해줘. 설명이나 코드블록 없이 JSON만 반환해줘.
**scripts 배열은 반드시 {scene_count}개만 포함해야 하며, {scene_count}개보다 많거나 적으면 안 돼. 예시는 형식 참고용일 뿐이고, 실제 개수는 반드시 {scene_count}개여야 해.**
**scripts 배열의 원소 개수는 반드시 {scene_count}개여야 하며, {scene_count}개가 아니면 잘못된 응답이야.**

예시(형식 참고용, 실제 개수는 위 지침을 따를 것):
{{
  "title": "교대역 스키당",
  "scripts": [
    {{"script": "교대역에 5년 연속 블루리본 샤실을 아시고 계셨나요?"}},
    {{"script": "가게가 정말 넓고 쾌적한 스키당 메뉴 추천 드립니다."}},
    {{"script": "2인세트 : 59,000원\\n매콤한 맛에 밥 한 그릇 뚝딱입니다!"}},
    {{"script": "세트에 포함되어 있는 카라아케인데 꼭 시켜드세요."}},
    {{"script": "청첩장 모임으로 제격입니다. 꼭 방문해 보세요."}}
  ]
}}


블로그 글:
{text}
"""


GENERAL_PROMPT = """
아래 블로그 글을 바탕으로, 유튜브 쇼츠 영상에 어울리는 제목과 스크립트를 자동으로 만들어줘.

타이틀 : 본문의 핵심 키워드 1~2개로 짧고 명확하게 만들어줘. 한국어 일반 톤.
   예: "양양 서핑 후기", "VS Code 단축키 꿀팁", "초보를 위한 코딩 입문", "강릉 1박2일 여행"

- 훅(첫 문장) 작성 지침:
{hook_prompt}

- 스크립트 작성 Tip :
첫번째 스크립트는 위 훅 지침을 참고해서 가장 강렬한 한 마디로 시작해서 이목을 끌어야 해.
중간 스크립트들은 본문의 핵심 정보 또는 인상 깊은 포인트 위주로.
마지막 스크립트는 깔끔하게 마무리하는 말투로.

- 주의 사항 :
줄바꿈이 필요한 부분은 반드시 \\n(역슬래시+n)으로 표기해줘. 실제 엔터(줄바꿈)는 사용하지 마.
각 줄은 20자 내외의 자연스러운 한두 문장으로 작성해줘.
설명이나 순서 안내 문구는 넣지 마.
말투는 너무 딱딱하지 않게! 유튜브 쇼츠에서 재미있게 볼 수 있도록 위트있고 센스 있게 써줘. 한국어 해요체.
맛집·음식점·메뉴·가격 같은 표현은 본문에 없으면 사용하지 마.

- 출력 형식
아래는 예시이고, 반드시 예시와 같이 JSON 객체 형태로 반환해줘. 설명이나 코드블록 없이 JSON만 반환해줘.
**scripts 배열은 반드시 {scene_count}개만 포함해야 하며, {scene_count}개보다 많거나 적으면 안 돼. 예시는 형식 참고용일 뿐이고, 실제 개수는 반드시 {scene_count}개여야 해.**
**scripts 배열의 원소 개수는 반드시 {scene_count}개여야 하며, {scene_count}개가 아니면 잘못된 응답이야.**

예시(형식 참고용, 실제 개수는 위 지침을 따를 것):
{{
  "title": "양양 서핑 후기",
  "scripts": [
    {{"script": "파도 위에서 만난 강원도, 양양 서핑 후기예요."}},
    {{"script": "초보도 30분이면 보드 위에 설 수 있어요."}},
    {{"script": "강사님이 자세부터 차근차근 알려줘요."}},
    {{"script": "하루 일정에 2시간이면 충분히 즐길 수 있어요."}},
    {{"script": "다음 주말, 양양 한 번 가보는 거 어때요?"}}
  ]
}}


블로그 글:
{text}
"""


def _generate_with_claude(prompt, schema):
    """Claude Sonnet 으로 title+scripts JSON 텍스트 생성. refusal 시 None.

    schema: build_shorts_output_schema(scene_count) 로 생성된 scene_count-aware 스키마.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    # Sonnet 5 는 adaptive thinking 이 기본이라 max_tokens 에 사고 토큰 여유가 필요.
    # effort=low: 파이프라인 지연을 gpt-3.5 수준으로 유지.
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": schema},
        },
        system="당신은 유능한 영상 스크립트 작가입니다.",
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        print("Claude 응답 거부 (refusal)")
        return None
    return next(b.text for b in response.content if b.type == "text").strip()


def _generate_with_openai(prompt):
    """OpenAI fallback — ANTHROPIC_API_KEY 미설정 배포 환경에서 기존 동작 유지.

    구조화 출력(JSON 스키마)을 쓰지 않으므로 scene_count 개수 강제가 안 됨 —
    후처리 패딩/절단(_normalize_scripts)에 전적으로 의존 (architecture.md §3-3).
    """
    import openai

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 유능한 영상 스크립트 작가입니다."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=700,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def _normalize_scripts(scripts: list, scene_count: int) -> list:
    """scripts 배열 길이를 scene_count(N)에 정확히 맞춘다.

    architecture.md §3-4 — 기존 "6개면 인덱스4 제거" 같은 특수 분기는 완전히 제거.
    N=6 처럼 6이 정상값일 수 있는 케이스와 충돌하기 때문. 초과분은 뒤에서 자르고,
    부족분은 빈 스크립트로 패딩한다.
    """
    if len(scripts) > scene_count:
        scripts = scripts[:scene_count]
    while len(scripts) < scene_count:
        scripts.append({"script": ""})
    return scripts


def summarize_for_shorts_sets(
    text,
    category: str = "restaurant",
    scene_count: int = 5,
    hook_prompt: str = "",
):
    """카테고리 × 컨셉 샘플 두 축을 동시에 반영해 쇼츠용 title+scripts(N개) 생성.

    ANTHROPIC_API_KEY 가 있으면 Claude Sonnet, 없으면 기존 OpenAI 로 동작.

    Args:
        text: 블로그 본문
        category: 'restaurant' (맛집, classifier.py 자동 분류) 또는 'general' (일반 블로그)
        scene_count: N — 선택된 concept_sample 의 scene_count (기본 5, 하위호환용)
        hook_prompt: 선택된 concept_sample 의 훅 작성 지침 (concept_samples.py)
    """
    template = RESTAURANT_PROMPT if category == "restaurant" else GENERAL_PROMPT
    prompt = template.format(text=text, scene_count=scene_count, hook_prompt=hook_prompt)
    schema = build_shorts_output_schema(scene_count)
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            content = _generate_with_claude(prompt, schema)
        else:
            print("[summarize] ANTHROPIC_API_KEY 미설정 — OpenAI fallback 사용")
            content = _generate_with_openai(prompt)
        if content is None:
            return "", []
        print("모델 응답:", content)
    except Exception as e:
        print("모델 API 호출 실패:", e)
        title = ""
        scripts = []
        return title, scripts
    try:
        obj = json.loads(content)
        title = obj.get("title", "")
        scripts = _normalize_scripts(obj.get("scripts", []), scene_count)
    except Exception:
        try:
            json_str = extract_json_from_codeblock(content)
            fixed_content = json_str.replace('\n', '\\n')
            fixed_content = fix_json_keys(fixed_content)
            obj = json.loads(fixed_content)
            title = obj.get("title", "")
            scripts = _normalize_scripts(obj.get("scripts", []), scene_count)
        except Exception as e:
            print(f"Claude 응답 파싱 실패: {e}")
            title = ""
            scripts = []
    return title, scripts
