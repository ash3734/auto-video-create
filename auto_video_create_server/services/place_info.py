"""맛집 정보카드용 가게 정보 뽑기 (2026-10-18, 백로그 2-1 정보카드 배치).

유저가 "맛집 정보카드" 배치를 고를 때만 부른다 — 모든 영상에 돌리면 쓰지도 않을 호출에
돈과 시간을 쓴다. 뽑은 값은 화면에서 유저가 고칠 수 있다 (틀린 주소가 영상에 박히면 안 된다).

글에 없는 건 지어내지 않는다 — 비워 두면 카드에서 그 줄이 빠진다. "지어내지 않는다"는
서비스 원칙과 같은 이유다.
"""
from __future__ import annotations

import json
import os

from .layouts import clean_place

MODEL = "gpt-4.1-mini"
TIMEOUT_SECONDS = 15        # API Gateway 29초 안에서 넉넉히
MAX_INPUT = 4000

PROMPT = """다음 블로그 글에서 소개하는 가게 정보를 뽑아줘. JSON 하나만 출력.
{"name": 가게 이름, "location": 위치(동네 이름이나 짧은 주소, 25자 이내), "price": 대표 메뉴와 가격(25자 이내)}
글에 나오지 않는 값은 지어내지 말고 빈 문자열로 둬.

글:
"""


def extract_place(text: str) -> dict:
    """{"name","location","price"} — 실패하거나 글이 비면 전부 빈 문자열."""
    text = (text or "").strip()
    if not text or not os.environ.get("OPENAI_API_KEY"):
        return clean_place(None)
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=TIMEOUT_SECONDS, max_retries=0)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": PROMPT + text[:MAX_INPUT]}],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0,
        )
        return clean_place(json.loads(resp.choices[0].message.content or "{}"))
    except Exception as e:
        # 못 뽑으면 빈 칸으로 — 유저가 직접 채우면 된다. 영상 제작을 막을 일이 아니다.
        print(f"[place_info] 추출 실패 (빈 칸으로): {e}")
        return clean_place(None)
