"""AI analysis via Grok (xAI) and Gemini (Google)."""

from __future__ import annotations

import json
from app.config import GROK_API_KEY, GEMINI_API_KEY

ANALYSIS_PROMPT = """You are a stock market analyst AI. Analyze the following sentiment data and provide a trading recommendation.

TICKER: {ticker}
SENTIMENT DATA:
{data}

Respond in EXACTLY this JSON format (no markdown, no code blocks, just raw JSON):
{{"score": <-100 to 100>, "recommendation": "<strong_buy|buy|hold|sell|strong_sell>", "reasoning": "<2-3 sentences>", "insight": "<additional perspective>", "confidence": <0.0 to 1.0>}}"""


async def analyze_with_grok(ticker: str, sentiment: dict) -> dict | None:
    if not GROK_API_KEY:
        return None
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
    prompt = ANALYSIS_PROMPT.format(ticker=ticker, data=json.dumps(sentiment.get("sources", {}), indent=2))

    try:
        resp = await client.chat.completions.create(
            model="grok-3-fast",
            messages=[
                {"role": "system", "content": "You are a financial analyst with X/Twitter access. Respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        content = resp.choices[0].message.content or "{}"
        tokens = resp.usage.total_tokens if resp.usage else 0
        parsed = json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
        return {
            "ticker": ticker,
            "provider": "grok",
            "model": "grok-3-fast",
            "score": parsed.get("score", 0),
            "recommendation": parsed.get("recommendation", "hold"),
            "reasoning": parsed.get("reasoning", ""),
            "insight": parsed.get("insight", ""),
            "confidence": parsed.get("confidence", 0),
            "tokens_used": tokens,
        }
    except Exception as e:
        return {"ticker": ticker, "provider": "grok", "error": str(e)}


async def analyze_with_gemini(ticker: str, sentiment: dict) -> dict | None:
    if not GEMINI_API_KEY:
        return None
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = ANALYSIS_PROMPT.format(ticker=ticker, data=json.dumps(sentiment.get("sources", {}), indent=2))

    try:
        resp = await model.generate_content_async(prompt)
        content = resp.text or "{}"
        cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        tokens = resp.usage_metadata.total_token_count if resp.usage_metadata else 0
        return {
            "ticker": ticker,
            "provider": "gemini",
            "model": "gemini-2.0-flash",
            "score": parsed.get("score", 0),
            "recommendation": parsed.get("recommendation", "hold"),
            "reasoning": parsed.get("reasoning", ""),
            "insight": parsed.get("insight", ""),
            "confidence": parsed.get("confidence", 0),
            "tokens_used": tokens,
        }
    except Exception as e:
        return {"ticker": ticker, "provider": "gemini", "error": str(e)}


async def full_analysis(ticker: str, sentiment: dict) -> dict:
    import asyncio

    grok_task = asyncio.create_task(analyze_with_grok(ticker, sentiment))
    gemini_task = asyncio.create_task(analyze_with_gemini(ticker, sentiment))

    grok = await grok_task
    gemini = await gemini_task

    # Check if both agree on a strong signal
    proposal = None
    if (
        grok and "error" not in grok
        and gemini and "error" not in gemini
        and abs(grok["score"]) > 50
        and abs(gemini["score"]) > 50
        and (grok["score"] > 0) == (gemini["score"] > 0)
    ):
        from app.services.buffett import find_cedear
        action = "buy" if grok["score"] > 0 else "sell"
        cedear = find_cedear(ticker)
        proposal = {
            "action": action,
            "ticker": cedear["cedear"] if cedear else ticker,
            "market": "bCBA" if cedear else "nYSE",
            "avg_score": round((grok["score"] + gemini["score"]) / 2, 1),
            "grok_rec": grok["recommendation"],
            "gemini_rec": gemini["recommendation"],
        }

    return {"grok": grok, "gemini": gemini, "proposal": proposal}
