import os
import openai
from dotenv import load_dotenv
import json
import re

load_dotenv()

def extract_title_and_scripts(content):
    # JSON 객체에서 title과 scripts 추출
    try:
        obj = json.loads(content)
        title = obj.get("title", "")
        scripts = obj.get("scripts", [])
        return title, scripts
    except Exception as e:
        raise ValueError(f"OpenAI 응답에서 title/scripts 추출 실패: {content}")

def summarize_for_shorts_sets(text, title, first_script):
    """
    블로그 본문을 유튜브 쇼츠 영상 스크립트로 요약
    :param text: 블로그 본문 텍스트
    :param title: 영상 제목(사용자 입력)
    :param first_script: 첫 번째 스크립트(사용자 입력)
    :return: 쇼츠용 요약 스크립트 (문자열)
    """
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = f"""
아래 블로그 글을 바탕으로, 유튜브 쇼츠 영상(30초 분량)에 어울리는 스크립트를 4줄로 만들어줘.
각 줄은 다음 역할을 반드시 지켜서 작성해줘:
1번째 줄: 대표 메뉴 한 가지를 임팩트 있게 소개 (30자 내외, 아래 형식)
2번째 줄: 또 다른 메뉴를 임팩트 있게 소개 (30자 내외, 아래 형식)
3번째 줄: 또 다른 메뉴를 임팩트 있게 소개 (30자 내외, 아래 형식)
4번째 줄: 가게 정보를 보여주며 추천 멘트로 마무리

2~3번째 줄(메뉴 설명)은 반드시 아래와 같은 형식으로 작성해줘:
메뉴명 : 가격\n설명
(예시: 불고기덮밥 : 9,000원\n달콤짭짤한 소스에 밥이 쏙쏙 들어가요.)

줄바꿈이 필요한 부분은 반드시 \\n(역슬래시+n)으로 표기해줘. 실제 엔터(줄바꿈)는 사용하지 마.

각 줄은 30자 내외의 자연스러운 한두 문장으로 작성해줘.
설명이나 순서 안내 문구는 넣지 마.

특히, 스크립트의 말투는 너무 딱딱하지 않게! 유튜브 쇼츠에서 재미있게 볼 수 있도록 위트있고 센스 있게 써줘.

아래는 예시이고, 예시와 같이 JSON 객체 형태로 반환해줘. 설명이나 코드블록 없이 JSON만 반환해줘.

{{
  "scripts": [
    {{"script": "불고기덮밥 : 9,000원\\n달콤짭짤한 소스에 밥이 쏙쏙 들어가요.!"}},
    {{"script": "제육볶음 : 8,500원\\n매콤한 맛에 밥 한 그릇 뚝딱 입니다.!"}},
    {{"script": "돈까스 : 8,000원\\n겉바속촉, 소스 듬뿍 들어가요."}},
    {{"script": "가성비 최고 맛집, 꼭 들러보세요!"}}
  ]
}}

블로그 글:
{text}
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 유능한 영상 스크립트 작가입니다."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=700,
        temperature=0.7,
    )
    content = response.choices[0].message.content.strip()
    print("OpenAI 응답:", content)  # 응답 확인용

    try:
        obj = json.loads(content)
        scripts = obj.get("scripts", [])
    except Exception:
        # 줄바꿈을 \\n으로 치환 후 재시도
        fixed_content = content.replace('\n', '\\n')
        try:
            obj = json.loads(fixed_content)
            scripts = obj.get("scripts", [])
        except Exception as e:
            raise ValueError(f"OpenAI 응답에서 scripts 추출 실패: {content}")

    # title, first_script는 사용자가 입력한 값 사용
    return title, [
        {"script": first_script},
        *scripts
    ]

if __name__ == "__main__":
    blog_text = "여기에 테스트용 블로그 본문을 입력하세요."
    title = input("제목을 입력하세요: ")
    first_script = input("첫 번째 스크립트를 입력하세요: ")
    result_title, scripts = summarize_for_shorts_sets(blog_text, title, first_script)
    print(result_title, scripts) 