# app/database.py

"""
database.py
-----------
Responsabilidade única: persistir cada evento de requisição, e também
guardar as métricas consolidadas diárias (batch rollup).

Por que SQLite aqui e não Postgres/Kafka ainda: você está em fase de
DESENVOLVIMENTO LOCAL. A arquitetura de produção (Kafka -> consumer ->
Postgres/Timescale) fica documentada no README como evolução planejada.
"""

import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "cost_guard.db"


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                user_id TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                cached INTEGER NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL NOT NULL
            )
        """)
        conn.commit()


def init_daily_metrics_table() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                date TEXT PRIMARY KEY,
                total_requests INTEGER NOT NULL,
                total_cost_usd REAL NOT NULL,
                cache_hits INTEGER NOT NULL,
                rate_limited INTEGER NOT NULL,
                budget_blocked INTEGER NOT NULL,
                avg_latency_ms REAL NOT NULL,
                computed_at REAL NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def log_event(
    user_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    cached: bool,
    status: str,
    latency_ms: float,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO events
                (timestamp, user_id, model, prompt_tokens, completion_tokens,
                 cost_usd, cached, status, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(), user_id, model, prompt_tokens, completion_tokens,
                cost_usd, int(cached), status, latency_ms,
            ),
        )
        conn.commit()