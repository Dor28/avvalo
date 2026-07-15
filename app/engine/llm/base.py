"""Provider contracts for the LLM stage."""

from typing import Protocol

from pydantic import BaseModel, Field

from app.engine.types import DraftOutput


class LLMResponse(BaseModel):
    """Parsed model response plus token usage."""

    draft: DraftOutput
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class LLMProvider(Protocol):
    """Async provider interface shared by hosted and local OpenAI-compatible LLMs."""

    async def analyze(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        max_output_tokens: int,
    ) -> LLMResponse:
        """Return a parsed draft for the supplied prompt."""


class LLMProviderError(RuntimeError):
    """Raised when a provider call fails before a usable draft is returned.

    ``args[0]`` may carry provider response text and must never reach logs,
    events, or alerts. Only the structured, content-free fields are loggable:
    ``error_code`` (the underlying exception class name, e.g. ``RateLimitError``)
    and ``status_code`` (the HTTP status, when the failure had one).
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class LLMResponseFormatError(LLMProviderError):
    """Raised when the provider returns non-JSON or schema-invalid content."""
