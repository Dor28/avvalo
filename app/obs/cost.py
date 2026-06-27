"""LLM token-cost accounting."""

from app.config import Settings


def estimate_llm_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    in_rate_per_m: float,
    out_rate_per_m: float,
) -> float:
    """Calculate USD cost from token counts and per-million-token rates."""

    return round(
        (input_tokens / 1_000_000 * in_rate_per_m)
        + (output_tokens / 1_000_000 * out_rate_per_m),
        6,
    )


def compute_cost(
    input_tokens: int,
    output_tokens: int,
    in_rate_per_m: float,
    out_rate_per_m: float,
) -> float:
    """Compatibility wrapper for the technical-plan cost formula."""

    return estimate_llm_cost_usd(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        in_rate_per_m=in_rate_per_m,
        out_rate_per_m=out_rate_per_m,
    )


def estimate_llm_cost_from_settings(
    *,
    input_tokens: int,
    output_tokens: int,
    settings: Settings,
) -> float:
    """Calculate LLM cost using configured provider rates."""

    return estimate_llm_cost_usd(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        in_rate_per_m=settings.llm_in_rate_per_m,
        out_rate_per_m=settings.llm_out_rate_per_m,
    )
