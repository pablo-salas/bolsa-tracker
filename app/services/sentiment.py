"""Sentiment aggregation from StockTwits, Reddit, Finnhub."""

from __future__ import annotations

import base64
import httpx

from app.config import (
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    REDDIT_USERNAME, REDDIT_PASSWORD,
    FINNHUB_API_KEY,
)

# ── StockTwits (no auth required) ─────────────────────────


async def stocktwits_sentiment(ticker: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json")
        if r.status_code != 200:
            return {"ticker": ticker, "score": 0, "bullish": 0, "bearish": 0, "total": 0, "error": r.text}
        data = r.json()

    messages = data.get("messages", [])
    bullish = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
    bearish = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
    total = bullish + bearish
    score = ((bullish - bearish) / total * 100) if total > 0 else 0

    return {"ticker": ticker, "score": round(score, 1), "bullish": bullish, "bearish": bearish, "total": total}


async def stocktwits_trending() -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://api.stocktwits.com/api/2/trending/symbols.json")
        if r.status_code != 200:
            return []
        return r.json().get("symbols", [])


# ── Reddit ────────────────────────────────────────────────

_reddit_token: str = ""
_reddit_expires: float = 0


async def _reddit_auth() -> str:
    global _reddit_token, _reddit_expires
    import time
    if _reddit_token and time.time() < _reddit_expires:
        return _reddit_token
    if not REDDIT_CLIENT_ID:
        raise ValueError("REDDIT_CLIENT_ID not set")

    creds = base64.b64encode(f"{REDDIT_CLIENT_ID}:{REDDIT_CLIENT_SECRET}".encode()).decode()
    async with httpx.AsyncClient() as c:
        r = await c.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "password", "username": REDDIT_USERNAME, "password": REDDIT_PASSWORD},
            headers={"Authorization": f"Basic {creds}", "User-Agent": "BolsaTracker/1.0"},
        )
        r.raise_for_status()
        data = r.json()
    _reddit_token = data["access_token"]
    _reddit_expires = time.time() + data.get("expires_in", 3600) - 60
    return _reddit_token


async def reddit_sentiment(ticker: str, subreddits: list[str] | None = None) -> list[dict]:
    subs = subreddits or ["wallstreetbets", "stocks", "investing"]
    results = []
    try:
        token = await _reddit_auth()
    except Exception:
        return [{"subreddit": s, "ticker": ticker, "mentions": 0, "score": 0, "error": "auth failed"} for s in subs]

    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}", "User-Agent": "BolsaTracker/1.0"}, timeout=15) as c:
        for sub in subs:
            try:
                r = await c.get(f"https://oauth.reddit.com/r/{sub}/search.json", params={"q": f"${ticker} OR {ticker}", "sort": "new", "t": "day", "limit": 25})
                if r.status_code != 200:
                    results.append({"subreddit": sub, "ticker": ticker, "mentions": 0, "score": 0})
                    continue
                posts = r.json().get("data", {}).get("children", [])
                mentions = len(posts)
                total_score = sum(p["data"].get("score", 0) for p in posts)
                avg = total_score / mentions if mentions else 0
                results.append({"subreddit": sub, "ticker": ticker, "mentions": mentions, "total_score": total_score, "avg_score": round(avg, 1), "score": round(min(100, max(-100, avg)), 1)})
            except Exception:
                results.append({"subreddit": sub, "ticker": ticker, "mentions": 0, "score": 0})
    return results


# ── Finnhub ───────────────────────────────────────────────


async def finnhub_sentiment(ticker: str) -> dict:
    if not FINNHUB_API_KEY:
        return {"ticker": ticker, "score": 0, "error": "no api key"}

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"https://finnhub.io/api/v1/stock/social-sentiment", params={"symbol": ticker, "token": FINNHUB_API_KEY})
        if r.status_code != 200:
            return {"ticker": ticker, "score": 0, "error": r.text}
        data = r.json()

    reddit_data = data.get("reddit", [])
    twitter_data = data.get("twitter", [])

    pos = sum(d.get("positiveMention", 0) for d in reddit_data + twitter_data)
    neg = sum(d.get("negativeMention", 0) for d in reddit_data + twitter_data)
    total = pos + neg
    score = ((pos - neg) / total * 100) if total > 0 else 0

    return {
        "ticker": ticker,
        "score": round(score, 1),
        "reddit_mentions": sum(d.get("mention", 0) for d in reddit_data),
        "twitter_mentions": sum(d.get("mention", 0) for d in twitter_data),
    }


# ── Aggregator ────────────────────────────────────────────

WEIGHTS = {"stocktwits": 0.35, "reddit": 0.35, "finnhub": 0.30}


async def aggregate_sentiment(ticker: str) -> dict:
    import asyncio

    st_task = asyncio.create_task(stocktwits_sentiment(ticker))
    rd_task = asyncio.create_task(reddit_sentiment(ticker)) if REDDIT_CLIENT_ID else None
    fh_task = asyncio.create_task(finnhub_sentiment(ticker)) if FINNHUB_API_KEY else None

    st = await st_task
    rd = (await rd_task) if rd_task else None
    fh = (await fh_task) if fh_task else None

    sources: dict = {"stocktwits": st}
    if rd is not None:
        sources["reddit"] = rd
    if fh is not None:
        sources["finnhub"] = fh

    # Weighted composite
    weighted = 0.0
    total_weight = 0.0
    total_mentions = st.get("total", 0)
    available = 1

    if "error" not in st:
        weighted += st["score"] * WEIGHTS["stocktwits"]
        total_weight += WEIGHTS["stocktwits"]

    if rd:
        reddit_score = sum(r.get("score", 0) for r in rd) / max(len(rd), 1)
        reddit_mentions = sum(r.get("mentions", 0) for r in rd)
        total_mentions += reddit_mentions
        if not any("error" in r for r in rd):
            weighted += reddit_score * WEIGHTS["reddit"]
            total_weight += WEIGHTS["reddit"]
            available += 1

    if fh and "error" not in fh:
        weighted += fh["score"] * WEIGHTS["finnhub"]
        total_weight += WEIGHTS["finnhub"]
        total_mentions += fh.get("reddit_mentions", 0) + fh.get("twitter_mentions", 0)
        available += 1

    composite = weighted / total_weight if total_weight > 0 else 0
    confidence = (available / 3) * 0.5 + min(1, total_mentions / 50) * 0.5

    from datetime import datetime, timezone
    return {
        "ticker": ticker,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "composite_score": round(composite, 1),
        "confidence": round(confidence, 2),
        "total_mentions": total_mentions,
    }
