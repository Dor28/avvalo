"""Shared Avvalo analysis engine package."""

from app.engine.pipeline import run_check
from app.engine.types import (
    CheckInput,
    CheckResult,
    CheckStatus,
    DraftOutput,
    InputType,
    Language,
    RuleHit,
    Signal,
)

__all__ = [
    "CheckInput",
    "CheckResult",
    "CheckStatus",
    "DraftOutput",
    "InputType",
    "Language",
    "RuleHit",
    "Signal",
    "run_check",
]
