import os
import openai
from dotenv import load_dotenv
import json
import re

load_dotenv()

def extract_json_from_codeblock(content):
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
    if match:
        return match.group(1)
    return content

def fix_json_keys(json_str):
    # { key: value } → { "key": value }
    json_str = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)
    return json_str

def summarize_for_shorts_sets(text):
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    prompt = f"""
아래 블로그 글을 바탕으로, 유튜브 쇼츠 영상에 어울리는 제목과 스크립트를 자동으로 만들어줘.

타이틀 : '무슨무슨역 상호명' 또는 '무슨무슨동 상호명' 형식으로 생성해줘. (예: '교대역 스키당', '압구정동 저스트스테이크')
타이틀은 블로그 본문에서 역/동/상호명을 추출해서 만들어줘. 만약 역/동 정보가 없으면 상호명만 사용해줘.

- 스크립트 작성 Tip :
첫번째 스크립트는 제일 강렬하게 어필해서 이목을 끌 수 있게 하면 좋아.
메뉴에 대한 가격과 설명이 들어가면 좋아
마지막 스크립트는 마무리하는 말투로 작성해줘.

- 주의 사항 : 
줄바꿈이 필요한 부분은 반드시 \\n(역슬래시+n)으로 표기해줘. 실제 엔터(줄바꿈)는 사용하지 마.
각 줄은 20자 내외의 자연스러운 한두 문장으로 작성해줘.
설명이나 순서 안내 문구는 넣지 마.
특히, 스크립트의 말투는 너무 딱딱하지 않게! 유튜브 쇼츠에서 재미있게 볼 수 있도록 위트있고 센스 있게 써줘.

- 출력 혁식
아래는 예시이고, 반드시 예시와 같이 JSON 객체 형태로 반환해줘. 설명이나 코드블록 없이 JSON만 반환해줘.
**scripts 배열은 반드시 5개만 포함해야 하며, 5개보다 많거나 적으면 안 돼. 6개 이상, 4개 이하로 반환하면 안 되고, 반드시 5개만 반환해야 해. 예시와 개수가 다르면 잘못된 응답이야.**
**scripts 배열의 원소 개수는 반드시 5개여야 하며, 5개가 아니면 잘못된 응답이야. 반드시 예시와 개수, 구조가 일치해야 해.**

예시:
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
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 유능한 영상 스크립트 작가입니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=700,
            temperature=0.7,
        )
        print("OpenAI 원시 응답:", response)
        try:
            content = response.choices[0].message.content.strip()
            print("OpenAI 응답:", content)
        except Exception as e:
            print("OpenAI 응답 content 파싱 실패:", e)
            title = ""
            scripts = []
            return title, scripts
    except Exception as e:
        print("OpenAI API 호출 실패:", e)
        title = ""
        scripts = []
        return title, scripts
    try:
        obj = json.loads(content)
        title = obj.get("title", "")
        scripts = obj.get("scripts", [])

        # scripts가 6개면 마지막(5번 인덱스)을 빼고 0~4번(총 5개)만 남김
        if len(scripts) == 6:
            print(f"[경고] GPT가 6개의 스크립트를 반환했습니다. 5번째(인덱스 4) 스크립트를 제외합니다.")
            scripts = [scripts[0], scripts[1], scripts[2], scripts[3], scripts[5]]
        # 5개 초과(7개 이상)면 앞 5개만 사용
        elif len(scripts) > 5:
            print(f"[경고] GPT가 {len(scripts)}개의 스크립트를 반환했습니다. 앞 5개만 사용합니다.")
            scripts = scripts[:5]
        # 5개 미만이면 빈 문자열로 채움
        while len(scripts) < 5:
            scripts.append({"script": ""})
    except Exception:
        try:
            json_str = extract_json_from_codeblock(content)
            fixed_content = json_str.replace('\n', '\\n')
            fixed_content = fix_json_keys(fixed_content)
            obj = json.loads(fixed_content)
            title = obj.get("title", "")
            scripts = obj.get("scripts", [])

            # scripts가 6개면 마지막(5번 인덱스)을 빼고 0~4번(총 5개)만 남김
            if len(scripts) == 6:
                print(f"[경고] GPT가 6개의 스크립트를 반환했습니다. 5번째(인덱스 4) 스크립트를 제외합니다.")
                scripts = [scripts[0], scripts[1], scripts[2], scripts[3], scripts[5]]
            # 5개 초과(7개 이상)면 앞 5개만 사용
            elif len(scripts) > 5:
                print(f"[경고] GPT가 {len(scripts)}개의 스크립트를 반환했습니다. 앞 5개만 사용합니다.")
                scripts = scripts[:5]
            # 5개 미만이면 빈 문자열로 채움
            while len(scripts) < 5:
                scripts.append({"script": ""})
        except Exception as e:
            print(f"OpenAI 응답 파싱 실패: {e}")
            title = ""
            scripts = []
    return title, scripts
