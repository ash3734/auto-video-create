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

def summarize_for_shorts_sets(text):
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    prompt = f"""
아래 블로그 글을 바탕으로, 유튜브 쇼츠 영상(20초 분량)에 어울리는 제목과 스크립트를 자동으로 만들어줘.

- title은 반드시 '무슨무슨역 상호명' 또는 '무슨무슨동 상호명' 형식으로 생성해줘. (예: '교대역 스키당', '압구정동 저스트스테이크')
- 첫 번째 스크립트는 반드시 '무슨무슨역 맛집 상호명 방문후기 입니다.', '무슨무슨동 맛집 상호명 방문후기 입니다.' 형식으로 생성해줘. (예: '교대역 맛집 스키당 방문후기 입니다.')
- title과 첫 번째 스크립트는 블로그 본문에서 역/동/상호명을 추출해서 만들어줘. 만약 역/동 정보가 없으면 상호명만 사용해줘.

그리고, 쇼츠용 스크립트 4줄을 아래와 같이 만들어줘:
1번째 줄: 대표 메뉴 한 가지를 임팩트 있게 소개 (20자 내외, 아래 형식)
2번째 줄: 또 다른 메뉴를 임팩트 있게 소개 (20자 내외, 아래 형식)
3번째 줄: 또 다른 메뉴를 임팩트 있게 소개 (20자 내외, 아래 형식)
4번째 줄: 가게 정보를 보여주며 추천 멘트로 마무리

2~3번째 줄(메뉴 설명)은 반드시 아래와 같은 형식으로 작성해줘:
메뉴명 : 가격\\n설명
(예시: 불고기덮밥 : 9,000원\\n달콤짭짤한 소스에 밥이 쏙쏙 들어가요!)

각 줄은 반드시 **문장이 완성되게** 끝내야 해. (예: '달콤 고소한 맛!'처럼 끝내지 말고, '달콤 고소한 맛이 일품이에요!'처럼 완성된 문장으로 끝내.)

줄바꿈이 필요한 부분은 반드시 \\n(역슬래시+n)으로 표기해줘. 실제 엔터(줄바꿈)는 사용하지 마.

각 줄은 20자 내외의 자연스러운 한두 문장으로 작성해줘.
설명이나 순서 안내 문구는 넣지 마.

특히, 스크립트의 말투는 너무 딱딱하지 않게! 유튜브 쇼츠에서 재미있게 볼 수 있도록 위트있고 센스 있게 써줘.

아래는 예시이고, 예시와 같이 JSON 객체 형태로 반환해줘. 설명이나 코드블록 없이 JSON만 반환해줘.

{{
  "title": "교대역 스키당",
  "first_script": "교대역 맛집 스키당 방문후기 입니다.",
  "scripts": [
    {{"script": "불고기덮밥 : 9,000원\\n달콤짭짤한 소스에 밥이 쏙쏙 들어가요!"}},
    {{"script": "제육볶음 : 8,500원\\n매콤한 맛에 밥 한 그릇 뚝딱입니다!"}},
    {{"script": "돈까스 : 8,000원\\n겉은 바삭, 속은 촉촉해서 정말 맛있어요!"}},
    {{"script": "가성비 최고 맛집, 꼭 들러보세요!"}}
  ]
}}

반드시 위 형식의 JSON으로 title, first_script, scripts(4개)를 반환해 주세요. 4개 미만이면 빈 문자열로 채워주세요.

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
    except Exception:
        try:
            json_str = extract_json_from_codeblock(content)
            fixed_content = json_str.replace('\n', '\\n')
            obj = json.loads(fixed_content)
            title = obj.get("title", "")
            scripts = obj.get("scripts", [])
        except Exception as e:
            print(f"OpenAI 응답 파싱 실패: {e}")
            title = ""
            scripts = []
    return title, scripts

if __name__ == "__main__":
    blog_text = "여기에 테스트용 블로그 본문을 입력하세요."
    title, scripts = summarize_for_shorts_sets(blog_text)
    print(title, scripts)
