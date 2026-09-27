import time
import random
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis

from app.pricing import estimate_cost, estimate_tokens, real_cost
from app.cache import get_cached_response, set_cached_response
from app.rate_limit import check_rate_limit
from app.budget import check_and_reserve_budget, reconcile_budget
from app.database import init_db, log_event, init_daily_metrics_table

redis_client: Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = Redis(host="localhost", port=6379, decode_responses=True)
    init_db()
    init_daily_metrics_table()
    yield
    await redis_client.aclose()


app = FastAPI(title="AI Cost Guard", lifespan=lifespan)


class ChatRequest(BaseModel):
    user_id: str
    model: str
    prompt: str
    max_tokens: int = 512


async def call_mock_llm(model: str, prompt: str, max_tokens: int) -> tuple[str, int, int]:
    await asyncio.sleep(random.uniform(0.05, 0.4))
    fake_response = f"[resposta simulada para: {prompt[:40]}...]"
    prompt_tokens = estimate_tokens(prompt)
    completion_tokens = random.randint(20, max_tokens)
    return fake_response, prompt_tokens, completion_tokens


@app.post("/v1/chat/completions")
async def proxy_completion(payload: ChatRequest):
    start = time.perf_counter()

     #RATE LIMIT
    try:
        await check_rate_limit(redis_client, payload.user_id)
    except HTTPException as e:
        _log_and_raise(payload, start, cached=False, status="rate_limited", cost=0.0, exc=e)

    #CACHE
    cached = await get_cached_response(redis_client, payload.model, payload.prompt)
    if cached:
        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            user_id=payload.user_id, model=payload.model,
            prompt_tokens=estimate_tokens(payload.prompt), completion_tokens=0,
            cost_usd=0.0, cached=True, status="success", latency_ms=latency_ms,
        )
        return {"response": cached, "cached": True, "cost_usd": 0.0}

    #BUDGET
    estimated = estimate_cost(payload.model, payload.prompt, payload.max_tokens)
    try:
        await check_and_reserve_budget(redis_client, payload.user_id, estimated)
    except HTTPException as e:
        _log_and_raise(payload, start, cached=False, status="budget_blocked", cost=0.0, exc=e)

    #CHAMADA AO LLM
    response_text, prompt_tokens, completion_tokens = await call_mock_llm(
        payload.model, payload.prompt, payload.max_tokens
    )

    #RECONCILIAÇÃO E CACHE
    final_cost = real_cost(payload.model, prompt_tokens, completion_tokens)
    await reconcile_budget(redis_client, payload.user_id, estimated, final_cost)
    await set_cached_response(redis_client, payload.model, payload.prompt, response_text)

    latency_ms = (time.perf_counter() - start) * 1000
    log_event(
        user_id=payload.user_id, model=payload.model,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        cost_usd=final_cost, cached=False, status="success", latency_ms=latency_ms,
    )

    return {
        "response": response_text,
        "cached": False,
        "cost_usd": final_cost,
        "tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
    }


def _log_and_raise(payload: ChatRequest, start: float, cached: bool, status: str, cost: float, exc: HTTPException):
    latency_ms = (time.perf_counter() - start) * 1000
    log_event(
        user_id=payload.user_id, model=payload.model,
        prompt_tokens=estimate_tokens(payload.prompt), completion_tokens=0,
        cost_usd=cost, cached=cached, status=status, latency_ms=latency_ms,
    )
    raise exc


@app.get("/health")
async def health():
    return {"status": "ok"}