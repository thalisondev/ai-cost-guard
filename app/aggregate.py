"""
aggregate.py
------------
Calcula as métricas do dia e SALVA num registro consolidado.
Isso é o "batch job" -- roda de tempos em tempos, não a cada requisição.

Padrão conhecido no mercado como "batch rollup" ou "materialized
aggregate" -- pré-calcula números pesados uma vez, em vez de
recalcular do zero toda vez que alguém consulta.
"""

import time
from datetime import date
from app.database import get_connection


def compute_daily_metrics(target_date: str | None = None) -> dict:
    target_date = target_date or date.today().isoformat()

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total_requests,
                COALESCE(SUM(cost_usd), 0) as total_cost,
                COALESCE(SUM(cached), 0) as cache_hits,
                COALESCE(SUM(CASE WHEN status = 'rate_limited' THEN 1 ELSE 0 END), 0) as rate_limited,
                COALESCE(SUM(CASE WHEN status = 'budget_blocked' THEN 1 ELSE 0 END), 0) as budget_blocked,
                COALESCE(AVG(latency_ms), 0) as avg_latency
            FROM events
            WHERE date(timestamp, 'unixepoch') = ?
        """, (target_date,))
        row = cursor.fetchone()

        total_requests, total_cost, cache_hits, rate_limited, budget_blocked, avg_latency = row

        conn.execute("""
            INSERT INTO daily_metrics
                (date, total_requests, total_cost_usd, cache_hits,
                 rate_limited, budget_blocked, avg_latency_ms, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_requests = excluded.total_requests,
                total_cost_usd = excluded.total_cost_usd,
                cache_hits = excluded.cache_hits,
                rate_limited = excluded.rate_limited,
                budget_blocked = excluded.budget_blocked,
                avg_latency_ms = excluded.avg_latency_ms,
                computed_at = excluded.computed_at
        """, (
            target_date, total_requests, total_cost, cache_hits,
            rate_limited, budget_blocked, avg_latency, time.time(),
        ))
        conn.commit()

    return {
        "date": target_date,
        "total_requests": total_requests,
        "total_cost_usd": total_cost,
    }


if __name__ == "__main__":
    # permite rodar isso como script separado: python -m app.aggregate
    result = compute_daily_metrics()
    print(f"Métricas consolidadas para {result['date']}: {result}")