import sqlite3
import os
from pathlib import Path
from app.config import DATABASE_PATH

# Resolve DB path relative to project root
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_DB_PATH = str(_BASE_DIR / DATABASE_PATH) if not os.path.isabs(DATABASE_PATH) else DATABASE_PATH


def get_db() -> sqlite3.Connection:
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        total_value_ars REAL,
        total_value_usd REAL,
        buffett_pct REAL DEFAULT 70,
        sentiment_pct REAL DEFAULT 30,
        holdings TEXT NOT NULL DEFAULT '[]'
    );

    CREATE TABLE IF NOT EXISTS buffett_holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filing_date TEXT NOT NULL,
        quarter_end TEXT NOT NULL,
        accession_number TEXT NOT NULL,
        issuer TEXT NOT NULL,
        cusip TEXT NOT NULL,
        ticker TEXT,
        title_of_class TEXT NOT NULL,
        value_thousands REAL NOT NULL,
        shares INTEGER NOT NULL,
        share_type TEXT NOT NULL,
        change_type TEXT,
        change_shares INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        strategy TEXT NOT NULL,
        action TEXT NOT NULL,
        ticker TEXT NOT NULL,
        market TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        currency TEXT NOT NULL,
        total_amount REAL NOT NULL,
        iol_order_id TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        proposal_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS trade_proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        strategy TEXT NOT NULL,
        action TEXT NOT NULL,
        ticker TEXT NOT NULL,
        market TEXT NOT NULL,
        suggested_qty INTEGER NOT NULL,
        suggested_price REAL,
        currency TEXT NOT NULL,
        ai_reasoning TEXT NOT NULL DEFAULT '{}',
        sentiment_score REAL,
        status TEXT NOT NULL DEFAULT 'pending',
        approved_at TEXT,
        approved_qty INTEGER
    );

    CREATE TABLE IF NOT EXISTS sentiment_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        ticker TEXT NOT NULL,
        source TEXT NOT NULL,
        bullish_count INTEGER,
        bearish_count INTEGER,
        total_mentions INTEGER,
        sentiment_score REAL,
        raw_data TEXT
    );

    CREATE TABLE IF NOT EXISTS ai_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        ticker TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt TEXT NOT NULL,
        response TEXT NOT NULL,
        score REAL,
        recommendation TEXT,
        tokens_used INTEGER
    );

    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """
    )
    conn.commit()
    conn.close()
