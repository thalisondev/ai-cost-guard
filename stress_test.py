import asyncio
import aiohttp
import random
import time
import argparse

MODELS = ["gpt-4o", "gpt-4o-mini", "claude-sonnet-4-6", "claude-haiku-4-5"]
USERS = [f"user_{i}" for i in range(1, 21)] + ["user_abusivo_01"]

PROMPT_POOL = [
    "Explique o teorema de Bayes",
    "Resuma vantagens do PostgreSQL",
    "Escreva uma função Python de ordenação",
    "O que é rate limiting?",
    "Explique o padrão CQRS",
]


def build_payload() -> dict:
    use_repeated = random.random() < 0.35
    prompt = random.choice(PROMPT_POOL) if use_repeated else f"Prompt único #{random.randint(1, 10_000_000)}"
    return {
        "user_id": random.choice(USERS),
        "model": random.choice(MODELS),
        "prompt": prompt,
        "max_tokens": random.choice([256, 512, 1024]),
    }


async def fire(session, url, sem):
    payload = build_payload()
    async with sem:
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                await resp.text()
        except Exception:
            pass


async def main(url: str, total: int, concurrency: int):
    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        start = time.perf_counter()
        tasks = [fire(session, url, sem) for _ in range(total)]
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
    print(f"✅ {total} requisições em {elapsed:.2f}s ({total/elapsed:.1f} req/s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/v1/chat/completions")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(main(args.url, args.requests, args.concurrency))