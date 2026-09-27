import hashlib
from redis.asyncio import Redis # type: ignore


def _cache_key(model: str, prompt: str) -> str:
    raw = f"{model}:{prompt}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"cache:exact:{digest}"


async def get_cached_response(redis: Redis, model: str, prompt: str) -> str | None:
    key = _cache_key(model, prompt)
    return await redis.get(key)


async def set_cached_response(
    redis: Redis, model: str, prompt: str, response: str, ttl_seconds: int = 3600
) -> None:
    key = _cache_key(model, prompt)
    await redis.set(key, response, ex=ttl_seconds)