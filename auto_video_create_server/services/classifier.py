"""블로그 글 자동 분류 — 맛집(restaurant) vs 일반(general).

cycle-2 신규. ADR-2 (architecture.md) 참조.
GPT-3.5-turbo 한 번 호출로 분류. 비용 ~$0.0001/회 (무시 수준).
사용자에게 노출되지 않음. BE 내부 — summarize 프롬프트 분기에 사용.
"""
import os
from typing import Literal

import openai


def classify_blog(text: str) -> Literal["restaurant", "general"]:
    """본문 첫 500자 기반으로 맛집/일반 분류.

    실패 시 안전하게 'general' 로 fallback.
    """
    if not text or not text.strip():
        return "general"

    try:
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "다음 블로그 글이 음식점/맛집 후기인지 아닌지 판단해줘. "
                        "답은 반드시 'restaurant' 또는 'general' 한 단어만 출력."
                    ),
                },
                {"role": "user", "content": text[:500]},
            ],
            max_tokens=5,
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip().lower()
        if "restaurant" in answer:
            return "restaurant"
        return "general"
    except Exception as e:
        print(f"[classifier] 분류 실패 — general fallback: {e}")
        return "general"
