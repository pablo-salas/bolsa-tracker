"""BolsaTracker – FastAPI server."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import IOL_SANDBOX, PORT
from app.db import init_db, get_db
from app.services.iol import iol
from app.services import buffett, sentiment, ai

# Resolve paths relative to project root (bolsa-tracker/)
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(title="BolsaTracker", version="0.1.0")

# Serve static files and templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.on_event("startup")
async def startup():
    init_db()
    print(f"\n  BolsaTracker v0.1 – http://localhost:{PORT}")
    print(f"  Mode: {'SANDBOX' if IOL_SANDBOX else 'PRODUCTION'}\n")


# ── Pages ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "sandbox": IOL_SANDBOX})


# ── Portfolio API ─────────────────────────────────────────

@app.get("/api/portfolio/{pais}")
async def get_portfolio(pais: str):
    try:
        return await iol.get_portfolio(pais)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/account")
async def get_account():
    try:
        return await iol.get_account_status()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/portfolio/snapshots")
async def get_snapshots(limit: int = 30):
    db = get_db()
    rows = db.execute("SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── Buffett API ───────────────────────────────────────────

@app.get("/api/buffett/filings")
async def get_filings():
    try:
        return await buffett.get_latest_13f_filings(5)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/buffett/holdings")
async def get_buffett_holdings(quarter: str | None = None):
    db = get_db()
    if quarter:
        rows = db.execute("SELECT * FROM buffett_holdings WHERE quarter_end = ? ORDER BY value_thousands DESC", (quarter,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM buffett_holdings ORDER BY value_thousands DESC", ()).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/api/buffett/sync")
async def sync_buffett():
    try:
        filings = await buffett.get_latest_13f_filings(2)
        if not filings:
            return {"error": "No 13F filings found"}

        latest = filings[0]
        current = await buffett.parse_info_table(latest["info_table_url"])

        changes = {}
        if len(filings) > 1:
            previous = await buffett.parse_info_table(filings[1]["info_table_url"])
            changes = buffett.diff_holdings(current, previous)

        # Resolve CUSIPs to tickers
        cusips = [h["cusip"] for h in current]
        ticker_map = await buffett.cusip_to_ticker(cusips)

        # Store in DB
        db = get_db()
        # Clear old data for this quarter
        db.execute("DELETE FROM buffett_holdings WHERE quarter_end = ?", (latest["report_date"],))

        for h in current:
            ticker = ticker_map.get(h["cusip"], "")
            change = changes.get(h["cusip"], {})
            db.execute(
                """INSERT INTO buffett_holdings
                   (filing_date, quarter_end, accession_number, issuer, cusip, ticker,
                    title_of_class, value_thousands, shares, share_type, change_type, change_shares)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    latest["filing_date"], latest["report_date"], latest["accession_number"],
                    h["issuer"], h["cusip"], ticker, h["title_of_class"],
                    h["value"], h["shares"], h["share_type"],
                    change.get("change", "unknown"), change.get("change_shares", 0),
                ),
            )
        db.commit()
        db.close()

        return {
            "filing_date": latest["filing_date"],
            "quarter_end": latest["report_date"],
            "holdings_count": len(current),
            "new_positions": sum(1 for c in changes.values() if c.get("change") == "new"),
            "exits": sum(1 for c in changes.values() if c.get("change") == "exited"),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Sentiment API ─────────────────────────────────────────

@app.get("/api/sentiment/{ticker}")
async def get_sentiment(ticker: str):
    try:
        return await sentiment.aggregate_sentiment(ticker.upper())
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/sentiment/{ticker}/history")
async def get_sentiment_history(ticker: str, limit: int = 50):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM sentiment_data WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?",
        (ticker.upper(), limit),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── AI Analysis API ───────────────────────────────────────

@app.post("/api/analyze/{ticker}")
async def analyze_ticker(ticker: str):
    ticker = ticker.upper()
    try:
        sent = await sentiment.aggregate_sentiment(ticker)

        # Store sentiment
        db = get_db()
        db.execute(
            """INSERT INTO sentiment_data (timestamp, ticker, source, sentiment_score, total_mentions, raw_data)
               VALUES (?, ?, 'aggregated', ?, ?, ?)""",
            (sent["timestamp"], ticker, sent["composite_score"], sent["total_mentions"], json.dumps(sent["sources"])),
        )
        db.commit()

        # AI analysis
        analysis = await ai.full_analysis(ticker, sent)

        # Store AI results
        now = datetime.now(timezone.utc).isoformat()
        for provider_key in ("grok", "gemini"):
            result = analysis.get(provider_key)
            if result and "error" not in result:
                db.execute(
                    """INSERT INTO ai_analysis (timestamp, ticker, provider, model, prompt, response, score, recommendation, tokens_used)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (now, ticker, provider_key, result.get("model", ""), "sentiment_analysis",
                     json.dumps(result), result.get("score", 0), result.get("recommendation", ""), result.get("tokens_used", 0)),
                )

        # Create proposal if AI agrees
        if analysis.get("proposal"):
            p = analysis["proposal"]
            import yfinance as yf
            try:
                stock = yf.Ticker(ticker)
                price = stock.fast_info.get("lastPrice", 0)
            except Exception:
                price = 0

            expires = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
            db.execute(
                """INSERT INTO trade_proposals (created_at, expires_at, strategy, action, ticker, market,
                   suggested_qty, suggested_price, currency, ai_reasoning, sentiment_score, status)
                   VALUES (?, ?, 'sentiment', ?, ?, ?, 1, ?, ?, ?, ?, 'pending')""",
                (now, expires, p["action"], p["ticker"], p["market"], price,
                 "ARS" if p["market"] == "bCBA" else "USD",
                 json.dumps({"grok": analysis.get("grok"), "gemini": analysis.get("gemini"), "sentiment": {"score": sent["composite_score"], "confidence": sent["confidence"]}}),
                 sent["composite_score"]),
            )

        db.commit()
        db.close()

        return {"sentiment": sent, **analysis}
    except Exception as e:
        return {"error": str(e)}


# ── Proposals API ─────────────────────────────────────────

@app.get("/api/proposals")
async def get_proposals(status: str = "pending"):
    db = get_db()
    if status == "all":
        rows = db.execute("SELECT * FROM trade_proposals ORDER BY created_at DESC LIMIT 100").fetchall()
    else:
        rows = db.execute("SELECT * FROM trade_proposals WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.post("/api/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, qty: int | None = None):
    db = get_db()
    row = db.execute("SELECT * FROM trade_proposals WHERE id = ?", (proposal_id,)).fetchone()
    if not row:
        db.close()
        return {"error": "Proposal not found"}

    proposal = dict(row)
    if proposal["status"] != "pending":
        db.close()
        return {"error": f"Proposal is {proposal['status']}"}

    # Check expiration
    if datetime.fromisoformat(proposal["expires_at"]) < datetime.now(timezone.utc):
        db.execute("UPDATE trade_proposals SET status = 'expired' WHERE id = ?", (proposal_id,))
        db.commit()
        db.close()
        return {"error": "Proposal expired"}

    quantity = qty or proposal["suggested_qty"]
    now = datetime.now(timezone.utc)
    validez = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

    try:
        if proposal["action"] == "buy":
            result = await iol.buy(proposal["market"], proposal["ticker"], quantity, proposal["suggested_price"] or 0, "t2", validez)
        else:
            result = await iol.sell(proposal["market"], proposal["ticker"], quantity, proposal["suggested_price"] or 0, "t2", validez)

        order_id = str(result.get("numeroOperacion", ""))

        db.execute("UPDATE trade_proposals SET status = 'executed', approved_at = ?, approved_qty = ? WHERE id = ?",
                    (now.isoformat(), quantity, proposal_id))

        db.execute(
            """INSERT INTO trades (timestamp, strategy, action, ticker, market, quantity, price, currency, total_amount, iol_order_id, status, proposal_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'executed', ?)""",
            (now.isoformat(), proposal["strategy"], proposal["action"], proposal["ticker"],
             proposal["market"], quantity, proposal["suggested_price"] or 0,
             proposal["currency"], quantity * (proposal["suggested_price"] or 0),
             order_id, proposal_id),
        )
        db.commit()
        db.close()
        return {"order_id": order_id, "quantity": quantity}
    except Exception as e:
        db.close()
        return {"error": str(e)}


@app.post("/api/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: int):
    db = get_db()
    db.execute("UPDATE trade_proposals SET status = 'rejected' WHERE id = ?", (proposal_id,))
    db.commit()
    db.close()
    return {"success": True}


# ── Trades API ────────────────────────────────────────────

@app.get("/api/trades")
async def get_trades(strategy: str | None = None, limit: int = 100):
    db = get_db()
    if strategy:
        rows = db.execute("SELECT * FROM trades WHERE strategy = ? ORDER BY timestamp DESC LIMIT ?", (strategy, limit)).fetchall()
    else:
        rows = db.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ── Market Data API ───────────────────────────────────────

@app.get("/api/quote/{ticker}")
async def get_yahoo_quote(ticker: str):
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        return {
            "ticker": ticker,
            "price": info.get("lastPrice", 0),
            "previous_close": info.get("previousClose", 0),
            "market_cap": info.get("marketCap", 0),
            "currency": info.get("currency", "USD"),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/iol-quote/{mercado}/{simbolo}")
async def get_iol_quote(mercado: str, simbolo: str):
    try:
        return await iol.get_quote(mercado, simbolo)
    except Exception as e:
        return {"error": str(e)}


# ── Market Scan (auto-proposals from sentiment only) ──────

DEFAULT_WATCHLIST = ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","AMD","NFLX","TSLA","KO","BAC","AXP","OXY","CVX","JPM","V"]

SENTIMENT_THRESHOLD = 35  # |score| > 35 triggers a proposal
CAPITAL_USD = 20000
SENTIMENT_ALLOC = 0.30  # 30%
MAX_POSITION_PCT = 0.15  # max 15% of sentiment capital per trade


@app.post("/api/scan")
async def scan_market():
    """Scan watchlist tickers for sentiment, generate trade proposals automatically."""
    db = get_db()

    # Get watchlist from config or default
    row = db.execute("SELECT value FROM config WHERE key = 'watchlist'").fetchone()
    watchlist = json.loads(row["value"]) if row else DEFAULT_WATCHLIST

    results = []
    proposals_created = 0
    now_str = datetime.now(timezone.utc).isoformat()

    for ticker in watchlist:
        try:
            sent = await sentiment.aggregate_sentiment(ticker)

            # Store sentiment
            db.execute(
                """INSERT INTO sentiment_data (timestamp, ticker, source, bullish_count, bearish_count, total_mentions, sentiment_score, raw_data)
                   VALUES (?, ?, 'aggregated', ?, ?, ?, ?, ?)""",
                (sent["timestamp"], ticker,
                 sent["sources"].get("stocktwits", {}).get("bullish", 0),
                 sent["sources"].get("stocktwits", {}).get("bearish", 0),
                 sent["total_mentions"], sent["composite_score"],
                 json.dumps(sent["sources"])),
            )

            entry = {"ticker": ticker, "score": sent["composite_score"], "confidence": sent["confidence"], "mentions": sent["total_mentions"], "proposal": None}

            # Generate proposal if strong signal
            if abs(sent["composite_score"]) > SENTIMENT_THRESHOLD and sent["confidence"] > 0.2:
                action = "buy" if sent["composite_score"] > 0 else "sell"

                # Check we don't already have a pending proposal for this ticker
                existing = db.execute(
                    "SELECT id FROM trade_proposals WHERE ticker = ? AND status = 'pending'", (ticker,)
                ).fetchone()
                if existing:
                    entry["proposal"] = "already_pending"
                    results.append(entry)
                    continue

                # Get price from yfinance
                price = 0
                try:
                    import yfinance as yf
                    stock = yf.Ticker(ticker)
                    price = stock.fast_info.get("lastPrice", 0) or 0
                except Exception:
                    pass

                if price <= 0:
                    entry["proposal"] = "no_price"
                    results.append(entry)
                    continue

                # Calculate quantity based on 30% allocation
                sentiment_capital = CAPITAL_USD * SENTIMENT_ALLOC
                max_per_trade = sentiment_capital * MAX_POSITION_PCT
                qty = max(1, int(max_per_trade / price))

                cedear = buffett.find_cedear(ticker)
                market = "bCBA" if cedear else "nYSE"
                display_ticker = cedear["cedear"] if cedear else ticker

                expires = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()

                reasoning = {
                    "engine": "sentiment_scan",
                    "sentiment": {
                        "composite_score": sent["composite_score"],
                        "confidence": sent["confidence"],
                        "total_mentions": sent["total_mentions"],
                        "sources": {
                            k: {"score": v.get("score", 0)} if isinstance(v, dict) else {}
                            for k, v in sent["sources"].items()
                        },
                    },
                    "signal": f"{'Bullish' if action == 'buy' else 'Bearish'} signal: score {sent['composite_score']:+.1f} with {sent['confidence']:.0%} confidence across {sent['total_mentions']} mentions",
                }

                # If AI keys are available, try to get AI analysis too
                ai_grok = None
                ai_gemini = None
                try:
                    analysis = await ai.full_analysis(ticker, sent)
                    ai_grok = analysis.get("grok")
                    ai_gemini = analysis.get("gemini")
                    if ai_grok and "error" not in ai_grok:
                        reasoning["grok"] = {"score": ai_grok["score"], "recommendation": ai_grok["recommendation"], "reasoning": ai_grok.get("reasoning", "")}
                    if ai_gemini and "error" not in ai_gemini:
                        reasoning["gemini"] = {"score": ai_gemini["score"], "recommendation": ai_gemini["recommendation"], "reasoning": ai_gemini.get("reasoning", "")}
                except Exception:
                    pass

                db.execute(
                    """INSERT INTO trade_proposals (created_at, expires_at, strategy, action, ticker, market,
                       suggested_qty, suggested_price, currency, ai_reasoning, sentiment_score, status)
                       VALUES (?, ?, 'sentiment', ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (now_str, expires, action, display_ticker, market, qty, price,
                     "ARS" if market == "bCBA" else "USD",
                     json.dumps(reasoning), sent["composite_score"]),
                )
                proposals_created += 1
                entry["proposal"] = {"action": action, "ticker": display_ticker, "qty": qty, "price": price}

            results.append(entry)
        except Exception as e:
            results.append({"ticker": ticker, "score": 0, "error": str(e)})

    db.commit()
    db.close()

    # Sort by absolute score descending
    results.sort(key=lambda x: abs(x.get("score", 0)), reverse=True)

    return {
        "scanned": len(results),
        "proposals_created": proposals_created,
        "timestamp": now_str,
        "results": results,
    }


# ── Health ────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "sandbox": IOL_SANDBOX, "timestamp": datetime.now(timezone.utc).isoformat()}
