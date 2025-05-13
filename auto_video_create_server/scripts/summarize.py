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

def summarize_for_shorts_sets(text):
    """
    블로그 본문을 유튜브 쇼츠 영상 스크립트로 요약
    :param text: 블로그 본문 텍스트
    :return: 쇼츠용 요약 스크립트 (문자열)
    """
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = f"""
아래 블로그 글을 바탕으로, 유튜브 쇼츠 영상(30초 분량)에 어울리는 세련되고 자연스러운 스크립트를 5개 세트로 만들어줘.
각 세트는 5~7초 분량의 임팩트 있는 한두 문장으로, 너무 짧지 않게 20자 이상 50자 이내로 작성해.
각 대사에는 '첫 번째 대사' 등 순서 안내 문구를 절대 넣지 마.
전체적인 내용을 보고 영상의 분위기와 어울리는 세련된 제목도 5자에서 10자 이내로 지어줘.
아래와 같이 JSON 객체 형태로 반환해줘. 설명이나 코드블록 없이 JSON만 반환해줘.

{{
  "title": "남부터미널 맛집",
  "scripts": [
    {{"script": "남부터미널 맛집 나오리주물럭! 대기가 있을 정도로 인기 많은 곳이에요."}},
    {{"script": "셀프 시스템이라 원하는 만큼 반찬을 마음껏 즐길 수 있습니다."}},
    {{"script": "소프트 콘 아이스크림은 꼭 드셔보세요. 식사 후 디저트로 최고!"}},
    {{"script": "통마늘이 듬뿍 들어간 매콤 주물럭, 양도 푸짐해서 만족도가 높아요."}},
    {{"script": "남부터미널에서 특별한 한 끼를 원한다면 이곳을 추천합니다!"}}
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

    title, scripts = extract_title_and_scripts(content)
    return title, scripts 