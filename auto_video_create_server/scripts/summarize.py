import os
import openai
from dotenv import load_dotenv

load_dotenv()

def summarize_for_shorts(text):
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = (
        "다음 블로그 글을 유튜브 쇼츠 영상 스크립트로 3~5문장으로 요약해줘. "
        "짧고 임팩트 있게, 시청자의 흥미를 끌 수 있게 써줘.\n\n"
        f"블로그 글:\n{text}"
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 유능한 영상 스크립트 작가입니다."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()
