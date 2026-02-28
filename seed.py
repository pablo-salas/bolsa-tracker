"""Seed the DB with realistic mock data. Capital: $20,000 USD."""

import sqlite3
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "bolsa-tracker.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(str(DB_PATH))
conn.execute("PRAGMA journal_mode=WAL")

# ── Helpers ───────────────────────────────────────────────
now = datetime.now(timezone.utc)
def ts(days_ago=0, hours_ago=0):
    return (now - timedelta(days=days_ago, hours=hours_ago)).isoformat()

def usd(v): return round(v, 2)

# ── Config ────────────────────────────────────────────────
conn.execute("DELETE FROM config")
conn.executemany("INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?)", [
    ("capital_usd", "20000", ts()),
    ("buffett_pct", "70", ts()),
    ("sentiment_pct", "30", ts()),
    ("watchlist", json.dumps(["AAPL","MSFT","NVDA","GOOGL","AMZN","META","KO","BAC","AXP","OXY","CVX","JPM","V","BRK-B"]), ts()),
])

# ── Buffett Holdings (Q4 2025 - latest real filing) ──────
conn.execute("DELETE FROM buffett_holdings")
buffett_holdings = [
    ("APPLE INC", "037833100", "AAPL", "COM", 300000000, 75000000, "SH", "decreased", -25000000),
    ("BANK OF AMER CORP", "060505104", "BAC", "COM", 35000000, 680000000, "SH", "unchanged", 0),
    ("AMERICAN EXPRESS CO", "025816109", "AXP", "COM", 28000000, 151000000, "SH", "unchanged", 0),
    ("COCA COLA CO", "191216100", "KO", "COM", 25000000, 400000000, "SH", "unchanged", 0),
    ("CHEVRON CORP", "166764100", "CVX", "COM", 18000000, 119000000, "SH", "unchanged", 0),
    ("OCCIDENTAL PETE CORP", "674599105", "OXY", "COM", 13000000, 264000000, "SH", "increased", 12000000),
    ("KRAFT HEINZ CO", "500754106", "KHC", "COM", 11000000, 325000000, "SH", "unchanged", 0),
    ("MOODYS CORP", "615369105", "MCO", "COM", 10500000, 24700000, "SH", "unchanged", 0),
    ("DAVITA INC", "23918K108", "DVA", "COM", 5200000, 36100000, "SH", "unchanged", 0),
    ("VERISIGN INC", "92343E102", "VRSN", "COM", 3800000, 12800000, "SH", "unchanged", 0),
    ("VISA INC", "92826C839", "V", "COM", 3200000, 8300000, "SH", "decreased", -1500000),
    ("MASTERCARD INC", "57636Q104", "MA", "COM", 2900000, 3900000, "SH", "new", 3900000),
    ("AMAZON COM INC", "023135106", "AMZN", "COM", 2100000, 10000000, "SH", "new", 10000000),
    ("SIRIUS XM HOLDINGS", "82968B103", "SIRI", "COM", 1800000, 105000000, "SH", "unchanged", 0),
    ("NU HOLDINGS LTD", "67066G104", "NU", "COM", 1500000, 107000000, "SH", "decreased", -20000000),
    ("LIBERTY MEDIA CORP", "531229854", "LSXMA", "COM", 1200000, 60000000, "SH", "unchanged", 0),
    ("T-MOBILE US INC", "872590104", "TMUS", "COM", 4800000, 22400000, "SH", "increased", 4000000),
    ("CONSTELLATION BRANDS", "21036P108", "STZ", "COM", 2500000, 11400000, "SH", "new", 11400000),
]

for h in buffett_holdings:
    conn.execute(
        """INSERT INTO buffett_holdings
           (filing_date, quarter_end, accession_number, issuer, cusip, ticker,
            title_of_class, value_thousands, shares, share_type, change_type, change_shares)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-02-17", "2025-12-31", "0000950170-26-001234",
         h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], h[8]),
    )

# ── Portfolio Snapshots (last 30 days) ───────────────────
conn.execute("DELETE FROM portfolio_snapshots")
# Simulate $20k growing with some volatility
# MEP rate ~1200 ARS/USD
MEP = 1200
base_usd = 20000
for i in range(30, -1, -1):
    daily_change = random.uniform(-0.015, 0.02)  # -1.5% to +2%
    base_usd = base_usd * (1 + daily_change)
    ars = base_usd * MEP
    conn.execute(
        "INSERT INTO portfolio_snapshots (timestamp, total_value_ars, total_value_usd, buffett_pct, sentiment_pct, holdings) VALUES (?, ?, ?, 70, 30, ?)",
        (ts(i), usd(ars), usd(base_usd), json.dumps({"buffett_usd": usd(base_usd * 0.7), "sentiment_usd": usd(base_usd * 0.3)})),
    )
final_usd = base_usd

# ── Trades (simulated history) ────────────────────────────
conn.execute("DELETE FROM trades")
trades = [
    # Buffett strategy trades (quarterly rebalance)
    (28, "buffett", "buy", "AAPL", "bCBA", 50, 3200.0, "ARS", "executed"),
    (28, "buffett", "buy", "KO", "bCBA", 100, 850.0, "ARS", "executed"),
    (28, "buffett", "buy", "BAC", "bCBA", 80, 620.0, "ARS", "executed"),
    (28, "buffett", "buy", "AXP", "bCBA", 15, 4800.0, "ARS", "executed"),
    (28, "buffett", "buy", "CVX", "bCBA", 20, 2100.0, "ARS", "executed"),
    (28, "buffett", "buy", "OXY", "nYSE", 30, 52.40, "USD", "executed"),
    (28, "buffett", "buy", "AMZN", "nYSE", 10, 208.50, "USD", "executed"),
    (28, "buffett", "buy", "MA", "nYSE", 5, 528.30, "USD", "executed"),
    (28, "buffett", "buy", "TMUS", "nYSE", 8, 215.70, "USD", "executed"),
    (28, "buffett", "buy", "STZ", "nYSE", 12, 178.90, "USD", "executed"),
    # Sentiment strategy trades (intra-quarter)
    (21, "sentiment", "buy", "NVDA", "bCBA", 30, 18500.0, "ARS", "executed"),
    (18, "sentiment", "buy", "META", "bCBA", 10, 12800.0, "ARS", "executed"),
    (14, "sentiment", "sell", "META", "bCBA", 10, 13400.0, "ARS", "executed"),  # +4.7%
    (10, "sentiment", "buy", "GOOGL", "bCBA", 20, 2400.0, "ARS", "executed"),
    (7, "sentiment", "buy", "MSFT", "bCBA", 8, 9200.0, "ARS", "executed"),
    (5, "sentiment", "sell", "NVDA", "bCBA", 30, 19800.0, "ARS", "executed"),  # +7%
    (3, "sentiment", "buy", "AMD", "bCBA", 25, 2100.0, "ARS", "executed"),
    (1, "sentiment", "buy", "NFLX", "nYSE", 3, 985.20, "USD", "executed"),
]

for t in trades:
    total = t[5] * t[6]
    conn.execute(
        """INSERT INTO trades (timestamp, strategy, action, ticker, market, quantity, price, currency, total_amount, iol_order_id, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts(t[0]), t[1], t[2], t[3], t[4], t[5], t[6], t[7], usd(total), f"IOL-{random.randint(100000,999999)}", t[8]),
    )

# ── Sentiment Data (last 7 days, multiple tickers) ───────
conn.execute("DELETE FROM sentiment_data")
sentiment_tickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "META", "AMD", "NFLX", "AMZN", "TSLA"]
for ticker in sentiment_tickers:
    base_score = random.uniform(-30, 60)
    for i in range(7, -1, -1):
        for h in [10, 14, 18]:  # 3 readings per day
            score = base_score + random.uniform(-25, 25)
            score = max(-100, min(100, score))
            mentions = random.randint(5, 120)
            bullish = int(mentions * (0.5 + score / 200))
            bearish = mentions - bullish
            sources = {
                "stocktwits": {"score": round(score + random.uniform(-10, 10), 1), "bullish": bullish, "bearish": bearish},
                "finnhub": {"score": round(score + random.uniform(-15, 15), 1), "reddit_mentions": random.randint(10, 80), "twitter_mentions": random.randint(20, 200)},
            }
            conn.execute(
                """INSERT INTO sentiment_data (timestamp, ticker, source, bullish_count, bearish_count, total_mentions, sentiment_score, raw_data)
                   VALUES (?, ?, 'aggregated', ?, ?, ?, ?, ?)""",
                (ts(i, 24 - h), ticker, bullish, bearish, mentions, round(score, 1), json.dumps(sources)),
            )

# ── AI Analysis (recent) ─────────────────────────────────
conn.execute("DELETE FROM ai_analysis")
ai_tickers = [
    ("NVDA", 72, "strong_buy", "NVDA shows exceptional momentum with AI chip demand continuing to grow. Sentiment across all platforms is overwhelmingly bullish.", "DeepSeek concerns are overblown; NVDA's CUDA ecosystem moat remains unbreakable."),
    ("NVDA", 68, "buy", "Strong bullish sentiment driven by datacenter revenue growth expectations. Technical indicators confirm uptrend.", "Long-term AI infrastructure spending will benefit NVDA regardless of short-term fluctuations."),
    ("META", 45, "buy", "META's AI investments in Llama models and Reality Labs are generating positive sentiment. Ad revenue continues strong.", "Metaverse spending concerns have eased as AI narrative takes over."),
    ("META", 38, "buy", "Social media sentiment is positive on META's open-source AI strategy. Revenue beats expected.", "Meta's efficiency gains ('Year of Efficiency') continue to drive margins higher."),
    ("AMD", 55, "buy", "AMD gaining market share in datacenter GPUs. MI300X orders strong. Positive sentiment on X.", "AMD's competitive positioning against both NVDA and Intel is improving."),
    ("AMD", 48, "buy", "Reddit bullish on AMD's AI accelerator roadmap. StockTwits showing strong buy signals.", "Fundamentals support current valuation with P/E declining as earnings grow."),
    ("MSFT", 32, "buy", "MSFT benefits from Azure AI growth. Copilot adoption increasing. Steady institutional buying.", "Cloud computing revenue is the main growth driver with AI monetization still early."),
    ("MSFT", 28, "hold", "Mixed signals: strong cloud growth but Copilot monetization still unclear. Hold for now.", "Azure growth rate needs to reaccelerate to justify premium valuation."),
    ("NFLX", 61, "strong_buy", "NFLX crushed earnings. Ad tier growing faster than expected. Password sharing crackdown working.", "Global subscriber growth has room to run, especially in emerging markets."),
    ("NFLX", 55, "buy", "Strong content pipeline and live sports (WWE, NFL) driving subscriber growth. Positive across all sentiment sources.", "Advertising revenue could be a $5B+ business by 2027."),
    ("GOOGL", 25, "hold", "Search AI integration going well but antitrust concerns weigh on sentiment.", "YouTube and Cloud are the key growth vectors; search dominance faces regulatory risk."),
    ("GOOGL", 18, "hold", "Mixed sentiment: AI search is promising but DOJ antitrust case creates uncertainty.", "Gemini model improvements are closing the gap with OpenAI."),
    ("AAPL", -15, "hold", "iPhone sales flat in China. Apple Intelligence rollout slower than expected.", "Services revenue continues to grow but hardware cycle is mature."),
    ("AAPL", -22, "sell", "Bearish sentiment on China weakness. Huawei competition increasing.", "Apple's AI strategy lacks the ambition of competitors; Siri remains underwhelming."),
    ("TSLA", -35, "sell", "TSLA sentiment very negative. Brand damage from CEO controversies. European sales dropping.", "Autonomous driving promises remain unfulfilled. Competition intensifying globally."),
    ("TSLA", -42, "strong_sell", "X sentiment highly negative. Reddit bearish. Boycott mentions increasing.", "Fundamentals don't support current valuation. P/E remains elevated vs auto peers."),
]

for i, (ticker, score, rec, reasoning, insight) in enumerate(ai_tickers):
    provider = "grok" if i % 2 == 0 else "gemini"
    model = "grok-3-fast" if provider == "grok" else "gemini-2.0-flash"
    days_ago = (len(ai_tickers) - i) // 2
    tokens = random.randint(200, 450)
    response = json.dumps({"score": score, "recommendation": rec, "reasoning": reasoning, "insight": insight, "confidence": round(random.uniform(0.6, 0.95), 2)})
    conn.execute(
        """INSERT INTO ai_analysis (timestamp, ticker, provider, model, prompt, response, score, recommendation, tokens_used)
           VALUES (?, ?, ?, ?, 'sentiment_analysis', ?, ?, ?, ?)""",
        (ts(days_ago, random.randint(0, 12)), ticker, provider, model, response, score, rec, tokens),
    )

# ── Trade Proposals ───────────────────────────────────────
conn.execute("DELETE FROM trade_proposals")
proposals = [
    # Pending proposals (active)
    {
        "created": ts(0, 2), "expires": ts(0, -6),  # expires in 6 hours
        "action": "buy", "ticker": "NVDA", "market": "bCBA",
        "qty": 15, "price": 19200.0, "currency": "ARS",
        "score": 70, "status": "pending",
        "reasoning": {
            "grok": {"score": 72, "recommendation": "strong_buy", "reasoning": "NVDA shows exceptional momentum with AI chip demand. All sentiment sources bullish."},
            "gemini": {"score": 68, "recommendation": "buy", "reasoning": "Strong datacenter revenue growth. Technical indicators confirm uptrend."},
            "sentiment": {"score": 65.3, "confidence": 0.82},
        },
    },
    {
        "created": ts(0, 1), "expires": ts(0, -7),
        "action": "buy", "ticker": "NFLX", "market": "nYSE",
        "qty": 5, "price": 992.50, "currency": "USD",
        "score": 58, "status": "pending",
        "reasoning": {
            "grok": {"score": 61, "recommendation": "strong_buy", "reasoning": "NFLX crushed earnings. Ad tier growing fast. Password crackdown working."},
            "gemini": {"score": 55, "recommendation": "buy", "reasoning": "Strong content pipeline and live sports driving growth."},
            "sentiment": {"score": 54.7, "confidence": 0.76},
        },
    },
    # Historical proposals
    {
        "created": ts(5), "expires": ts(5, -8),
        "action": "buy", "ticker": "NVDA", "market": "bCBA",
        "qty": 30, "price": 18500.0, "currency": "ARS",
        "score": 62, "status": "executed",
        "reasoning": {"grok": {"score": 65, "recommendation": "buy", "reasoning": "AI momentum strong."}, "gemini": {"score": 60, "recommendation": "buy", "reasoning": "Datacenter growth."}},
    },
    {
        "created": ts(12), "expires": ts(12, -8),
        "action": "buy", "ticker": "META", "market": "bCBA",
        "qty": 10, "price": 12800.0, "currency": "ARS",
        "score": 52, "status": "executed",
        "reasoning": {"grok": {"score": 55, "recommendation": "buy"}, "gemini": {"score": 50, "recommendation": "buy"}},
    },
    {
        "created": ts(8), "expires": ts(8, -8),
        "action": "sell", "ticker": "META", "market": "bCBA",
        "qty": 10, "price": 13400.0, "currency": "ARS",
        "score": -55, "status": "executed",
        "reasoning": {"grok": {"score": -52, "recommendation": "sell"}, "gemini": {"score": -58, "recommendation": "sell"}},
    },
    {
        "created": ts(2), "expires": ts(2, -8),
        "action": "sell", "ticker": "TSLA", "market": "bCBA",
        "qty": 20, "price": 4500.0, "currency": "ARS",
        "score": -62, "status": "rejected",
        "reasoning": {"grok": {"score": -65, "recommendation": "strong_sell", "reasoning": "Brand damage severe."}, "gemini": {"score": -58, "recommendation": "sell", "reasoning": "Fundamentals weak."}},
    },
    {
        "created": ts(6), "expires": ts(5, -16),
        "action": "buy", "ticker": "AAPL", "market": "bCBA",
        "qty": 25, "price": 3100.0, "currency": "ARS",
        "score": 42, "status": "expired",
        "reasoning": {"grok": {"score": 52, "recommendation": "buy"}, "gemini": {"score": 48, "recommendation": "buy"}},
    },
]

for p in proposals:
    conn.execute(
        """INSERT INTO trade_proposals (created_at, expires_at, strategy, action, ticker, market,
           suggested_qty, suggested_price, currency, ai_reasoning, sentiment_score, status, approved_at, approved_qty)
           VALUES (?, ?, 'sentiment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (p["created"], p["expires"], p["action"], p["ticker"], p["market"],
         p["qty"], p["price"], p["currency"], json.dumps(p["reasoning"]),
         p["score"], p["status"],
         p["created"] if p["status"] == "executed" else None,
         p["qty"] if p["status"] == "executed" else None),
    )

conn.commit()

# ── Summary ───────────────────────────────────────────────
print(f"""
  Seed complete!

  Capital:           $20,000 USD (~{20000 * MEP:,.0f} ARS)
  Final value:       ${final_usd:,.2f} USD
  Portfolio snapshots: 31 days
  Buffett holdings:  {len(buffett_holdings)} positions (Q4 2025)
  Trades executed:   {len(trades)}
  Sentiment records: {len(sentiment_tickers) * 8 * 3}
  AI analyses:       {len(ai_tickers)}
  Trade proposals:   {len(proposals)} ({sum(1 for p in proposals if p['status']=='pending')} pending)
""")

conn.close()
