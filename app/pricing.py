PRICING_TABLE = {
    "gpt-4o":              (0.0050, 0.0150),
    "gpt-4o-mini":         (0.00015, 0.00060),
    "claude-sonnet-4-6":   (0.0030, 0.0150),
    "claude-haiku-4-5":    (0.0008, 0.0040),
}

DEFAULT_PRICE = (0.0010, 0.0020)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost(model: str, prompt: str, max_tokens: int) -> float:
    prompt_price, completion_price = PRICING_TABLE.get(model, DEFAULT_PRICE)
    prompt_tokens = estimate_tokens(prompt)
    completion_tokens = max_tokens
    cost = (prompt_tokens / 1000) * prompt_price + (completion_tokens / 1000) * completion_price
    return round(cost, 6)
def real_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_price, completion_price = PRICING_TABLE.get(model, DEFAULT_PRICE)
    cost = (prompt_tokens / 1000) * prompt_price + (completion_tokens / 1000) * completion_price
    return round(cost, 6)