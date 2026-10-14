import json
import os
import time
from decimal import Decimal
from typing import Any, Type
import httpx
from pydantic import BaseModel
from app.core.config import settings
from app.llm_gateway.base import BaseLLMAdapter, LLMResponse


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini models (gemini-1.5-pro, etc.)."""

    def __init__(self, model_name: str = "gemini-1.5-pro", api_key: str | None = None):
        resolved_key = api_key or getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        super().__init__(model_name=model_name, api_key=resolved_key)
        self.api_base = "https://generativelanguage.googleapis.com/v1beta"

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY chưa được cấu hình. "
                "Vui lòng thiết lập GEMINI_API_KEY hoặc OPENAI_COMPATIBLE_API_KEY (OpenRouter) trên Railway Variables."
            )

        start_time = time.perf_counter()
        url = f"{self.api_base}/models/{self.model_name}:generateContent?key={self.api_key}"

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.2),
            },
        }

        if response_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        candidate = data["candidates"][0]["content"]["parts"][0]["text"]
        content = candidate

        parsed = None
        if response_schema or kwargs.get("parse_json", True):
            try:
                parsed = json.loads(content)
            except Exception:
                pass

        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", len(system_prompt.split()) + len(user_prompt.split()))
        completion_tokens = usage.get("candidatesTokenCount", len(content.split()))
        total_tokens = prompt_tokens + completion_tokens

        # Gemini pricing approx $0.00125 per 1k input, $0.005 per 1k output
        cost = Decimal(str(round((prompt_tokens * 0.00000125) + (completion_tokens * 0.000005), 6)))

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
