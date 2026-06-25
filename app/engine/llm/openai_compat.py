"""OpenAI-compatible chat-completions provider.

This adapter is intentionally host-agnostic: OpenRouter, Together, Fireworks,
vLLM, and local Ollama all enter through the same OpenAI-compatible surface.
"""

from __future__ import annotations

import json
from typing import Any

from openai import APIError, AsyncOpenAI
from pydantic import SecretStr, ValidationError

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
            raise LLMProviderError(str(exc)) from exc

        content = _response_content(response)
        draft = _parse_draft(content)
        usage = getattr(response, "usage", None)
        return LLMResponse(
            draft=draft,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )


def _response_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise LLMResponseFormatError("Provider response did not contain message content") from exc

    if not isinstance(content, str) or not content.strip():
        raise LLMResponseFormatError("Provider response content was empty")
    return content


def _parse_draft(content: str) -> DraftOutput:
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()

    try:
        data = json.loads(text)
        return DraftOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMResponseFormatError("Provider response did not match DraftOutput JSON") from exc
