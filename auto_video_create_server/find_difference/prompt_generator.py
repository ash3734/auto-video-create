import openai
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

SYSTEM_PROMPT = (
    "매일 새로운 '틀린그림 찾기' 이미지를 만들기 위한 프롬프트를 생성해줘. "
    "재미있고 다양한 상황, 계절, 트렌드 등을 반영해서 1문장으로 만들어줘. "
    "예시: '여름 해변에서 수영하는 아이들', '카페에서 커피를 마시는 사람들', '강아지와 고양이가 함께 노는 공원'"
)

def get_today_prompt():
    today = datetime.date.today().strftime("%Y-%m-%d")
    user_prompt = f"오늘 날짜는 {today}야. 오늘의 주제로 어울리는 틀린그림 찾기 프롬프트를 만들어줘."
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=50
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    print(get_today_prompt()) 