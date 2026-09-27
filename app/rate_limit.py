import time
from fastapi import HTTPException
from redis.asyncio import Redis


async def check_rate_limit(
    redis: Redis,
    user_id: str,
    max_requests: int = 20,
    window_seconds: int = 60,
) -> None:
    key = f"ratelimit:{user_id}"
    now = time.time()
    window_start = now - window_seconds

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {f"{now}": now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds)
    results = await pipe.execute()

    request_count = results[2]

    if request_count > max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit excedido: {request_count}/{max_requests} req em {window_seconds}s",
        )