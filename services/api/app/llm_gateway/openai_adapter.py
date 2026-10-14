import json
import os
import time
from decimal import Decimal
from typing import Any, Type
import httpx
from pydantic import BaseModel
from app.llm_gateway.base import BaseLLMAdapter, LLMResponse


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI models (GPT-4o, etc.)."""

    def __init__(self, model_name: str = "gpt-4o", api_key: str | None = None, api_base: str | None = None):
        super().__init__(model_name=model_name, api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.api_base = api_base or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError(f"API key is not configured for {self.model_name} (base: {self.api_base}).")

        start_time = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mathcouncil.ai",
            "X-Title": "Math Council Olympiad AI",
        }

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if not any(k in self.model_name.lower() for k in ["o1", "o3", "reasoner"]):
            payload["temperature"] = kwargs.get("temperature", 0.2)

        if response_schema:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
            if res.status_code >= 400:
                import logging
                logging.getLogger("llm_gateway.openai_adapter").error(
                    "OpenAIAdapter HTTP %d from %s/chat/completions: %s",
                    res.status_code,
                    self.api_base,
                    res.text,
                )
            res.raise_for_status()
            data = res.json()

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        choice = data["choices"][0]["message"]
        content = choice["content"]

        parsed = None
        if response_schema or kwargs.get("parse_json", True):
            try:
                parsed = json.loads(content)
            except Exception:
                pass

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        # Standard pricing: ~$0.005 / 1k input, $0.015 / 1k output
        cost = Decimal(str(round((prompt_tokens * 0.000005) + (completion_tokens * 0.000015), 6)))

        return LLMResponse(
            content=content,
            parsed_json=parsed,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            model_name=self.model_name,
        )
