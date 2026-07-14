"""블로그 글 자동 분류 — 맛집(restaurant) vs 일반(general).

cycle-2 신규. ADR-2 (architecture.md) 참조.
Claude Sonnet 한 번 호출로 분류 (ANTHROPIC_API_KEY 미설정 시 OpenAI fallback).
사용자에게 노출되지 않음. BE 내부 — summarize 프롬프트 분기에 사용.
"""
import os
from typing import Literal

import anthropic

CLAUDE_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "다음 블로그 글이 음식점/맛집 후기인지 아닌지 판단해줘. "
    "답은 반드시 'restaurant' 또는 'general' 한 단어만 출력."
)


def _classify_with_claude(text: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=10,
        # 한 단어 분류라 thinking 불필요 — 지연/토큰 최소화
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text[:500]}],
    )
    return next(b.text for b in resp.content if b.type == "text").strip().lower()


def _classify_with_openai(text: str) -> str:
    """OpenAI fallback — ANTHROPIC_API_KEY 미설정 배포 환경에서 기존 동작 유지."""
    import openai

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:500]},
        ],
        max_tokens=5,
        temperature=0,
    )
    return resp.choices[0].message.content.strip().lower()


def classify_blog(text: str) -> Literal["restaurant", "general"]:
    """본문 첫 500자 기반으로 맛집/일반 분류.

    실패 시 안전하게 'general' 로 fallback.
    """
    if not text or not text.strip():
        return "general"

    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            answer = _classify_with_claude(text)
        else:
            print("[classifier] ANTHROPIC_API_KEY 미설정 — OpenAI fallback 사용")
            answer = _classify_with_openai(text)
        if "restaurant" in answer:
            return "restaurant"
        return "general"
    except Exception as e:
        print(f"[classifier] 분류 실패 — general fallback: {e}")
        return "general"
