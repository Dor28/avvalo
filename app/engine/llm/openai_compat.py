"""OpenAI-compatible chat-completions provider.

This adapter is intentionally host-agnostic: OpenRouter, Together, Fireworks,
vLLM, and local Ollama all enter through the same OpenAI-compatible surface.
"""

from __future__ import annotations

import json
from typing import Any

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel, Field, SecretStr, ValidationError

from app.config import Settings
from app.engine.llm.base import LLMProviderError, LLMResponse, LLMResponseFormatError
from app.engine.types import DraftOutput


class OpenAICompatibleProvider:
    """Call a model through the OpenAI Chat Completions API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | SecretStr,
        model: str,
        timeout_s: float = 30.0,
        temperature: float = 0.2,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        self._client = client or AsyncOpenAI(
            base_url=base_url,
            api_key=key,
            timeout=timeout_s,
            max_retries=1,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenAICompatibleProvider:
        """Build the configured provider from process settings."""

        return cls(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
        )

    async def analyze(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        max_output_tokens: int,
    ) -> LLMResponse:
        """Call the model and parse its JSON response into ``DraftOutput``."""

        completion = await self.complete_json(
            system=system,
            user=user,
            schema=schema,
            max_output_tokens=max_output_tokens,
        )
        payload = completion.payload
        if "addressed_rule_ids" not in payload:
            # Preserve the validator's corrective-retry path: an omitted key is
            # equivalent to declaring that no authoritative rules were covered.
            payload = {**payload, "addressed_rule_ids": []}
        try:
            draft = DraftOutput.model_validate(payload)
        except ValidationError as exc:
            raise LLMResponseFormatError(
                "Provider response did not match DraftOutput JSON"
            ) from exc
        return LLMResponse(
            draft=draft,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        max_output_tokens: int,
    ) -> JSONCompletion:
        """Return generic JSON through the shared client for answer and router calls."""

        _ = schema  # JSON mode is the common denominator across configured hosts.
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self.temperature,
                max_tokens=max_output_tokens,
                response_format={"type": "json_object"},
            )
        except APIError as exc:
            status_code = getattr(exc, "status_code", None)
            raise LLMProviderError(
                str(exc),
                error_code=type(exc).__name__,
                status_code=status_code if isinstance(status_code, int) else None,
            ) from exc

        content = _response_content(response)
        try:
            payload = json.loads(_strip_json_fence(content))
        except json.JSONDecodeError as exc:
            raise LLMResponseFormatError("Provider response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise LLMResponseFormatError("Provider response JSON was not an object")
        usage = getattr(response, "usage", None)
        return JSONCompletion(
            payload=payload,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )


class JSONCompletion(BaseModel):
    """Generic JSON response plus provider token usage."""

    payload: dict[str, Any]
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


def _response_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise LLMResponseFormatError("Provider response did not contain message content") from exc

    if not isinstance(content, str) or not content.strip():
        raise LLMResponseFormatError("Provider response content was empty")
    return content


def _parse_draft(content: str) -> DraftOutput:
    try:
        data = json.loads(_strip_json_fence(content))
        return DraftOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMResponseFormatError("Provider response did not match DraftOutput JSON") from exc


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()
    return text
