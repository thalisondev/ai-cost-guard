# app/budget.py

import time
from fastapi import HTTPException
from redis.asyncio import Redis


def _budget_key(user_id: str) -> str:
    month_tag = time.strftime("%Y-%m")
    return f"budget:{user_id}:{month_tag}"


async def check_and_reserve_budget(
    redis: Redis,
    user_id: str,
    estimated_cost_usd: float,
    monthly_limit_usd: float = 10.0,
) -> None:
    key = _budget_key(user_id)
    current_spend = float(await redis.get(key) or 0.0)

    if current_spend + estimated_cost_usd > monthly_limit_usd:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Orçamento mensal excedido para '{user_id}': "
                f"${current_spend:.4f} + ${estimated_cost_usd:.4f} > ${monthly_limit_usd:.2f}"
            ),
        )

    await redis.incrbyfloat(key, estimated_cost_usd)
    await redis.expire(key, 60 * 60 * 24 * 35)


async def reconcile_budget(redis: Redis, user_id: str, estimated: float, real: float) -> None:
    diff = real - estimated
    if diff != 0:
        key = _budget_key(user_id)
        await redis.incrbyfloat(key, diff)


async def get_current_spend(redis: Redis, user_id: str) -> float:
    key = _budget_key(user_id)
    return float(await redis.get(key) or 0.0)