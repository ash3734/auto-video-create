import os
import anthropic
from dotenv import load_dotenv
import json
import re

load_dotenv()

CLAUDE_MODEL = "claude-sonnet-5"

# 구조화 출력 스키마 — Claude 가 항상 이 형태의 JSON 만 반환하도록 강제
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
        "seo": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "description_long": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "description", "description_long", "hashtags"],
            "additionalProperties": False,
        },
    },
    "required": ["title", "scripts", "seo"],
    "additionalProperties": False,
}

# VOC-2 (이미지 자동 매칭): 이미지 목록이 있을 때 쓰는 확장 스키마 —
# 스크립트별로 어울리는 이미지 번호(1-based)를 함께 받는다.
SHORTS_OUTPUT_SCHEMA_WITH_IMAGES = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "scripts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "script": {"type": "string"},
                    "image_index": {"type": ["integer", "null"]},
                },
                "required": ["script", "image_index"],
                "additionalProperties": False,
            },
        },
        "seo": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "description_long": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "description", "description_long", "hashtags"],
            "additionalProperties": False,
        },
    },
    "required": ["title", "scripts", "seo"],
    "additionalProperties": False,
}

# VOC-2: 기존 카테고리 프롬프트 뒤에 붙이는 이미지 매칭 부록.
# 기존 스크립트 생성 호출에 피기백 — 추가 API 호출 없음 (30초 타임아웃 안전).
IMAGE_MATCHING_ADDENDUM = """

- 이미지 자동 매칭 (추가 작업):
아래는 블로그 본문에서 추출한 이미지 목록이야. 번호는 1부터 시작해.
각 스크립트 내용에 가장 잘 어울리는 이미지 번호를 각 스크립트의 "image_index" 로 함께 반환해줘.
규칙:
1) 같은 번호를 두 번 이상 쓰지 마 (스크립트마다 서로 다른 이미지).
2) 어울리는 이미지가 정말 없으면 null 을 넣어.
3) scripts 의 각 원소는 {{"script": "...", "image_index": 번호 또는 null}} 형태여야 해.

이미지 목록:
{image_list}
"""


# 배포용 문구 (2026-08-30). 유저 요청: "제목 설명 태그 등등도 생성" —
# 만든 영상을 유튜브/인스타/틱톡/페이스북에 올릴 때 쓸 문구다.
# 기존 스크립트 생성 호출에 피기백 — 추가 API 호출 없음 (이미지 매칭과 같은 수법).
#
# 재료 3개만 만들고 플랫폼별 조립은 화면에서 한다. 플랫폼마다 따로 생성하면 호출이
# 4배가 되는데, 실제로 갈리는 건 "제목 칸이 따로 있는가"(유튜브만)와 해시태그 개수뿐이라
# 그럴 이유가 없다.
SEO_ADDENDUM = """

- 배포용 문구 (추가 작업):
이 영상을 SNS 에 올릴 때 쓸 문구도 함께 만들어줘. "seo" 키로 반환해.

  - title: 40자 이내. 사람들이 실제로 검색할 만한 말을 앞쪽에 두고,
    본문의 고유명사(지역·단지·상호·제품명)를 반드시 하나 이상 넣어줘.
    낚시성 표현은 쓰지 마.

  - description: 3~4문장, 한 문단. 인스타그램·페이스북에 쓸 것이라
    읽기 편한 말투로. 첫 문장만 봐도 무슨 영상인지 알 수 있게 써줘.

  - description_long: 유튜브 설명란용, 200~400자.
    유튜브는 설명란 글자로 영상을 이해하고 검색에 노출시키니 충분히 길게 써.
    이렇게 구성해줘 —
      1) 첫 두 줄: 무슨 영상인지 한눈에. (이 부분만 접히지 않고 먼저 보인다)
      2) 그 다음: 본문에서 뽑은 **구체적인 정보**를 자연스러운 문장으로.
         고유명사, 숫자, 지역, 조건 같은 걸 최대한 살려줘. 이런 말들이
         검색에 걸리는 실제 재료다.
      3) 마지막 한 줄: 영상에서 확인하라는 안내.
    빈 미사여구로 길이만 늘리지 마. 본문에 없는 사실을 지어내지도 마.

  - hashtags: **정확히 15개.** '#' 없이 단어만, 공백 없이.
    앞 3개는 가장 구체적인 것(지역명·상호명·제품명)으로 — 유튜브는 앞 3개만
    제목 위에 보인다. 뒤로 갈수록 넓은 주제어를 놓아줘.
    한글 위주로, 사람이 실제로 검색창에 칠 법한 말로 써.

형식: "seo": {{"title": "...", "description": "...", "description_long": "...",
              "hashtags": ["...", "..."]}}
"""


def _format_image_list_for_prompt(image_infos, limit=20):
    """image_infos → 프롬프트용 번호 목록 텍스트 (1-based, 최대 limit개)."""
    lines = []
    for i, info in enumerate(image_infos[:limit], start=1):
        desc = (info.get("caption") or "").strip() or (info.get("context") or "").strip() or "(설명 없음)"
        lines.append(f"[{i}] {desc[:80]}")
    return "\n".join(lines)

def build_shorts_output_schema(scene_count: int, with_images: bool = False) -> dict:
    """장면 수(N)에 맞춰 scripts 배열 길이를 강제하는 구조화 출력 스키마 생성.

    scene_count 선택 기능: 배열 길이가 더 이상 고정 5가 아니므로
    minItems/maxItems 를 N 으로 주입해 모델이 정확히 N개를 반환하게 한다.
    """
    import copy

    base = SHORTS_OUTPUT_SCHEMA_WITH_IMAGES if with_images else SHORTS_OUTPUT_SCHEMA
    schema = copy.deepcopy(base)
    schema["properties"]["scripts"]["minItems"] = scene_count
    schema["properties"]["scripts"]["maxItems"] = scene_count
    return schema


def _normalize_scripts(scripts, scene_count: int):
    """scripts 배열 길이를 scene_count(N)에 정확히 맞춘다.

    - N개 초과: 앞 N개만 사용 (단 N+1개면 마지막 원소를 버리는 대신 마무리 문장을 살림)
    - N개 미만: 빈 스크립트로 채움
    """
    if not isinstance(scripts, list):
        return [{"script": ""} for _ in range(scene_count)]

    if len(scripts) == scene_count + 1:
        # 기존 동작 계승: 하나 더 왔을 때는 마지막(마무리 멘트)을 살리고 직전 것을 버린다.
        print(f"[경고] 모델이 {len(scripts)}개를 반환했습니다. 끝에서 두 번째를 제외합니다.")
        scripts = scripts[: scene_count - 1] + [scripts[-1]]
    elif len(scripts) > scene_count:
        print(f"[경고] 모델이 {len(scripts)}개를 반환했습니다. 앞 {scene_count}개만 사용합니다.")
        scripts = scripts[:scene_count]

    while len(scripts) < scene_count:
        scripts.append({"script": ""})
    return scripts


# 배포용 문구의 안전 기본값. 모델이 안 주거나 형식이 어긋나도 영상 제작은 계속돼야 한다.
EMPTY_SEO = {"title": "", "description": "", "description_long": "", "hashtags": []}
MAX_HASHTAGS = 15


def normalize_seo(raw, fallback_title: str = "") -> dict:
    """모델이 준 seo 를 화면에 그대로 쓸 수 있는 형태로 다듬는다.

    문구가 없다고 영상 제작을 막지 않는다 — 부가 기능이므로 조용히 빈 값으로 흐른다.
    해시태그는 '#' 을 떼고 중복/빈 값을 제거한 뒤 개수를 제한한다. 모델이 '#여행' 처럼
    붙여서 줄 때가 있는데, 화면에서 다시 '#' 을 붙이므로 그대로 두면 '##여행' 이 된다.
    """
    if not isinstance(raw, dict):
        return {**EMPTY_SEO, "title": fallback_title or ""}

    title = raw.get("title")
    title = title.strip() if isinstance(title, str) else ""

    desc = raw.get("description")
    desc = desc.strip() if isinstance(desc, str) else ""

    # 유튜브 설명란용 긴 버전. 모델이 안 주면 짧은 설명으로 대신한다 —
    # 유튜브 탭이 빈 칸이 되는 것보다 짧게라도 채워 주는 편이 낫다.
    long_desc = raw.get("description_long")
    long_desc = long_desc.strip() if isinstance(long_desc, str) else ""
    if not long_desc:
        long_desc = desc

    tags, seen = [], set()
    for t in raw.get("hashtags") or []:
        if not isinstance(t, str):
            continue
        t = t.strip().lstrip("#").strip().replace(" ", "")
        if not t or t.lower() in seen:
            continue
        seen.add(t.lower())
        tags.append(t)
        if len(tags) >= MAX_HASHTAGS:
            break

    return {
        "title": title or (fallback_title or ""),
        "description": desc,
        "description_long": long_desc,
        "hashtags": tags,
    }


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
# - restaurant: 음식점 글 (역/동 + 상호명 제목, 메뉴·가격·맛)
# - general: 일반 블로그 글
#
# 2026-09-15 개정 — "문장이 별로"라는 PO 피드백. 이전 프롬프트의 결과를 보면
#   · "20자 내외"에 맞추느라 숫자·고유명사부터 버렸다 ("세 시간" → "경험")
#   · "위트있고 센스 있게"가 광고 문구를 낳았다 ("변신해요!", "끝!")
#   · 금지 기준이 없어 "공감되시죠?" 같은 빈 질문으로 칸을 채웠다
#   · 글쓴이 목소리가 사라지고 장면끼리 이어지지 않았다
# 길이를 늘리라고 강제하지 않는다 — 할 말이 없는 장면을 늘리면 빈 문장만 는다.
# 대신 "장면마다 본문의 구체적인 정보 하나"를 요구하고, 길이는 그 결과로 정해지게 둔다.
# 줄바꿈(\\n) 지시도 뺐다. 자막은 음성을 받아 따로 나뉘므로 효과가 없고 문장만 끊었다.

_COMMON_RULES = """
- 쓰지 말 것
빈 감탄과 과장 ("대박", "미쳤다", "끝!", "완전 강추"), 문장마다 느낌표
공감을 구하는 질문 ("공감되시죠?", "궁금하시죠?", "여러분도 가보실래요?")
본문에 없는 사실, 숫자, 평가
줄바꿈 문자, 이모지, 해시태그, 설명이나 순서 안내 문구

- 길이
한 장면은 한두 문장, 소리 내어 읽으면 2~5초 분량이야.
담을 정보가 적은 장면은 짧아도 괜찮아. 길이를 채우려고 말을 늘리지 마.
"""

RESTAURANT_PROMPT = """
아래 음식점 블로그 글을 유튜브 쇼츠 나레이션으로 바꿔줘. 제목과 장면별 스크립트를 만들어.

이 서비스는 블로거가 이미 쓴 글을 영상으로 한 번 더 쓰게 해주는 도구야.
스크립트는 새로 지어낸 광고 문구가 아니라, **글쓴이가 다녀온 곳을 짧게 말로 들려주는 것**이어야 해.

타이틀 : '무슨무슨역 상호명' 또는 '무슨무슨동 상호명' 형식. (예: '교대역 스키당', '압구정동 저스트스테이크')
본문에서 역/동/상호명을 추출해서 만들고, 역/동 정보가 없으면 상호명만 써.

- 장면마다 지킬 것
1. 본문에 나온 구체적인 정보를 하나씩 담아. 메뉴 이름, 가격, 양, 맛과 식감, 웨이팅, 위치, 분위기.
   "맛있어요", "분위기 좋아요"처럼 어느 가게에나 쓸 수 있는 문장은 쓰지 마.
2. 글쓴이의 시점과 말투를 살려. 직접 먹어본 사람의 말로. 해요체.
3. 장면들이 하나의 방문기로 이어지게 써. 본문 순서를 따르되,
   첫 장면은 이 가게에서 가장 눈에 띄는 구체적인 사실로 시작하고,
   마지막 장면은 재방문 의사나 추천 상황처럼 글쓴이의 결론으로 닫아.
""" + _COMMON_RULES + """
- 같은 내용, 나쁜 예 → 좋은 예
  "여기 진짜 맛있어요!" → "2인 세트가 59,000원인데, 매콤해서 밥 한 공기가 금방 비었어요."
  "분위기 최고!" → "가게가 넓어서 여럿이 모여도 여유 있게 앉았어요."
  "꼭 가보세요!" → "청첩장 모임 장소로 잡았는데 다들 만족했어요."

- 출력 형식
반드시 아래와 같은 JSON 객체로만 반환해줘. 설명이나 코드블록 없이 JSON만.
**scripts 배열은 반드시 {scene_count}개만 포함해야 하며, {scene_count}개보다 많거나 적으면 안 돼. 아래 예시는 형식 참고용일 뿐이고, 실제 개수는 반드시 {scene_count}개여야 해.**
**scripts 배열의 원소 개수는 반드시 {scene_count}개여야 하며, {scene_count}개가 아니면 잘못된 응답이야.**

예시(형식 참고용 — 개수는 {scene_count}개로 맞출 것):
{{
  "title": "교대역 스키당",
  "scripts": [
    {{"script": "교대역 스키당, 블루리본을 5년 연속 받은 곳이에요."}},
    {{"script": "가게가 넓고 쾌적해서 모임 자리로 편했어요."}},
    {{"script": "2인 세트가 59,000원인데, 매콤해서 밥 한 공기가 금방 비었어요."}},
    {{"script": "세트에 들어 있는 가라아게는 꼭 같이 드셔보세요."}},
    {{"script": "청첩장 모임으로 잡았는데 다들 만족하고 돌아갔어요."}}
  ]
}}


블로그 글:
{text}
"""


GENERAL_PROMPT = """
아래 블로그 글을 유튜브 쇼츠 나레이션으로 바꿔줘. 제목과 장면별 스크립트를 만들어.

이 서비스는 창작자가 이미 쓴 글을 영상으로 한 번 더 쓰게 해주는 도구야.
스크립트는 새로 지어낸 광고 문구가 아니라, **글쓴이가 자기 글을 짧게 말로 들려주는 것**이어야 해.

타이틀 : 본문의 핵심 키워드 1~2개로 짧고 명확하게. 한국어 일반 톤.
   예: "양양 서핑 후기", "VS Code 단축키 꿀팁", "초보를 위한 코딩 입문", "강릉 1박2일 여행"

- 장면마다 지킬 것
1. 본문에 나온 구체적인 정보를 하나씩 담아. 숫자, 이름, 장소, 가격, 시간, 글쓴이가 직접 겪은 일.
   "좋았어요", "도움이 돼요"처럼 어느 글에나 쓸 수 있는 문장은 쓰지 마.
2. 글쓴이의 시점과 말투를 살려. 글이 "제가"로 쓰였으면 "제가"로. 해요체.
3. 장면들이 하나의 이야기로 이어지게 써. 본문 순서를 따르되,
   첫 장면은 이 글에서 가장 궁금해지는 구체적인 사실로 시작하고,
   마지막 장면은 글의 결론이나 글쓴이의 한마디로 닫아.
4. 맛집·음식점·메뉴·가격 같은 표현은 본문에 없으면 쓰지 마.
""" + _COMMON_RULES + """
- 같은 내용, 나쁜 예 → 좋은 예
  "서핑, 생각보다 쉬워요!" → "초보인데도 30분 만에 보드 위에 섰어요."
  "강사님 최고예요!" → "강사님이 발 위치부터 하나하나 잡아줬어요."
  "여러분도 도전해 보실래요?" → "하루 2시간이면 충분해서 당일치기로도 괜찮아요."

- 출력 형식
반드시 아래와 같은 JSON 객체로만 반환해줘. 설명이나 코드블록 없이 JSON만.
**scripts 배열은 반드시 {scene_count}개만 포함해야 하며, {scene_count}개보다 많거나 적으면 안 돼. 아래 예시는 형식 참고용일 뿐이고, 실제 개수는 반드시 {scene_count}개여야 해.**

예시(형식 참고용 — 개수는 {scene_count}개로 맞출 것):
{{
  "title": "양양 서핑 후기",
  "scripts": [
    {{"script": "양양에서 서핑을 처음 배웠는데, 30분 만에 보드 위에 섰어요."}},
    {{"script": "강사님이 발 위치부터 하나하나 잡아줬어요."}},
    {{"script": "첫 파도는 세 번 연속 넘어졌지만, 네 번째에 끝까지 탔어요."}},
    {{"script": "강습 2시간이면 충분해서 오후엔 바닷가 카페에서 쉬었어요."}},
    {{"script": "다음엔 장비를 빌려서 혼자 타보려고요."}}
  ]
}}


블로그 글:
{text}
"""


def _generate_with_claude(prompt, schema=None):
    """Claude Sonnet 으로 title+scripts JSON 텍스트 생성. refusal 시 None."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    # Sonnet 5 는 adaptive thinking 이 기본이라 max_tokens 에 사고 토큰 여유가 필요.
    # effort=low: 파이프라인 지연을 gpt-3.5 수준으로 유지.
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": schema or SHORTS_OUTPUT_SCHEMA},
        },
        system="당신은 유능한 영상 스크립트 작가입니다.",
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        print("Claude 응답 거부 (refusal)")
        return None
    return next(b.text for b in response.content if b.type == "text").strip()


# 스크립트·배포용 문구를 만드는 모델 (2026-08-30).
#
# gpt-3.5-turbo 에서 옮겨왔다. 같은 블로그 글로 후보들을 나란히 돌려 정했다 —
#
#   gpt-3.5-turbo   유튜브 설명 115자(일반론)   4.0s   **JSON 파싱 실패**
#   gpt-4o-mini     185자                    11.6s   OK
#   gpt-4.1-mini    225자                     6.0s   OK   ← 선택
#   gpt-5-mini      출력 0자(추론이 예산 소진)   17.6s   실패
#
# 길이보다 **내용**이 갈렸다. gpt-3.5 는 "지하철역 접근성, 주차 시설 상태" 처럼
# 아무 글에나 붙는 말을 쓰는데, gpt-4.1-mini 는 본문에서 날짜·법원·감정가·평형·
# 랜드마크를 실제로 뽑아낸다. 사람이 검색하는 건 그런 말들이다.
#
# 더 중요한 건 안정성이다. 비교 중 gpt-3.5 가 배열 끝에 쉼표를 넣고 "seo" 를
# JSON 객체 **바깥**에 써서 파싱이 깨졌다. 그러면 우리 코드는 제목도 스크립트도
# 빈 값으로 돌려주고, 유저는 아무것도 없는 화면을 본다. 간헐적이라 더 나쁘다.
# (2026-08-29 8장면에서 제로폭 공백으로 스크립트가 채워진 것도 같은 뿌리로 보인다)
#
# 지연은 4.0s → 6.0s. Lambda 타임아웃 60초, 최근 1,970건의 실제 소요가
# 중앙값 0.2s / 최대 12s 라 여유 안에 있다. gpt-4o-mini(11.6s)는 그래서 뺐다.
OPENAI_MODEL = "gpt-4.1-mini"


def _generate_with_openai(prompt):
    """OpenAI fallback — ANTHROPIC_API_KEY 미설정 배포 환경에서 기존 동작 유지."""
    import openai

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "당신은 유능한 영상 스크립트 작가입니다."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2500,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def summarize_for_shorts_sets(text, category: str = "restaurant", image_infos=None,
                              scene_count: int = 5):
    """카테고리에 따라 다른 프롬프트로 쇼츠용 title+scripts(scene_count개) 생성.

    ANTHROPIC_API_KEY 가 있으면 Claude Sonnet, 없으면 기존 OpenAI 로 동작.

    VOC-2: image_infos 가 있으면 이미지 매칭 부록을 피기백 —
    scripts 각 원소에 image_index(1-based 또는 null) 가 포함될 수 있다.
    호출부(blog_shorts)가 꺼내 쓰고 FE 응답에서는 제거한다.

    scene_count: 유저가 고른 장면 수(4~8). 프롬프트/스키마/후처리 모두 이 값에 맞춘다.

    Args:
        text: 블로그 본문
        category: 'restaurant' (맛집, 기존) 또는 'general' (일반 블로그)
        image_infos: [{"url","caption","context"}, ...] 또는 None
        scene_count: 생성할 스크립트 개수 (기본 5 — 기존 동작)
    """
    template = RESTAURANT_PROMPT if category == "restaurant" else GENERAL_PROMPT
    prompt = template.format(text=text, scene_count=scene_count)
    with_images = False
    if image_infos:
        try:
            prompt += IMAGE_MATCHING_ADDENDUM.format(
                image_list=_format_image_list_for_prompt(image_infos)
            )
            with_images = True
        except Exception as e:
            # 이미지 부록 구성 실패 시 매칭 없이 기존 동작 (방어적)
            print(f"[summarize] 이미지 매칭 부록 구성 실패 — 매칭 없이 진행: {e}")
    prompt += SEO_ADDENDUM
    schema = build_shorts_output_schema(scene_count, with_images=with_images)
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            content = _generate_with_claude(prompt, schema=schema)
        else:
            print("[summarize] ANTHROPIC_API_KEY 미설정 — OpenAI fallback 사용")
            content = _generate_with_openai(prompt)
        if content is None:
            return "", [], dict(EMPTY_SEO)
        print("모델 응답:", content)
    except Exception as e:
        print("모델 API 호출 실패:", e)
        return "", [], dict(EMPTY_SEO)
    try:
        obj = json.loads(content)
        title = obj.get("title", "")
        scripts = _normalize_scripts(obj.get("scripts", []), scene_count)
        seo = normalize_seo(obj.get("seo"), fallback_title=title)
    except Exception:
        try:
            json_str = extract_json_from_codeblock(content)
            fixed_content = json_str.replace('\n', '\\n')
            fixed_content = fix_json_keys(fixed_content)
            obj = json.loads(fixed_content)
            title = obj.get("title", "")
            scripts = _normalize_scripts(obj.get("scripts", []), scene_count)
            seo = normalize_seo(obj.get("seo"), fallback_title=title)
        except Exception as e:
            print(f"Claude 응답 파싱 실패: {e}")
            title = ""
            scripts = []
            seo = dict(EMPTY_SEO)
    return title, scripts, seo
