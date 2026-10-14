import json
import os
import time
from decimal import Decimal
from typing import Any, Type
import httpx
from pydantic import BaseModel
from app.core.config import settings
from app.llm_gateway.base import BaseLLMAdapter, LLMResponse


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI models (GPT-4o, etc.)."""

    def __init__(self, model_name: str = "gpt-4o", api_key: str | None = None, api_base: str | None = None):
        resolved_key = api_key or getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
        resolved_base = api_base or getattr(settings, "OPENAI_API_BASE", None) or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        super().__init__(model_name=model_name, api_key=resolved_key)
        self.api_base = resolved_base

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError(
                f"Chưa cấu hình API Key cho model '{self.model_name}' (Endpoint: {self.api_base}). "
                "Vui lòng thiết lập OPENAI_API_KEY hoặc OPENAI_COMPATIBLE_API_KEY (OpenRouter) trên Railway Variables."
            )

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

        if response_schema and not any(k in self.model_name.lower() for k in ["reasoner"]):
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
        content = choice.get("content") or ""
        reasoning_content = choice.get("reasoning_content") or ""

        # Extract reasoning from <think>...</think> if not in reasoning_content
        import re
        if not reasoning_content and "<think>" in content:
            think_match = re.search(r"<think>(.*?)</think>", content, flags=re.DOTALL)
            if think_match:
                reasoning_content = think_match.group(1).strip()

        parsed = None
        if response_schema or kwargs.get("parse_json", True):
            try:
                cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
                if fence_match:
                    json_str = fence_match.group(1)
                else:
                    first_brace = cleaned.find("{")
                    last_brace = cleaned.rfind("}")
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        json_str = cleaned[first_brace : last_brace + 1]
                    else:
                        json_str = cleaned
                parsed = json.loads(json_str)
            except Exception:
                try:
                    parsed = json.loads(content)
                except Exception:
                    pass

        # Bóc tách reasoning tokens / thinking content vào lời giải
        if reasoning_content and isinstance(parsed, dict):
            parsed["reasoning_content"] = reasoning_content
            if "summary" in parsed and "Tư duy suy luận" not in str(parsed["summary"]):
                parsed["summary"] = (
                    f"**[Tư duy suy luận (DeepSeek Reasoner)]**:\n{reasoning_content}\n\n"
                    f"**[Tóm tắt phương pháp]**:\n{parsed['summary']}"
                )

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        # Standard pricing: ~$0.005 / 1k input, $0.015 / 1k output
        cost = Decimal(str(round((prompt_tokens * 0.000005) + (completion_tokens * 0.000015), 6)))

        return LLMResponse(
            content=content,
            parsed_json=parsed,
            reasoning_content=reasoning_content or None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            model_name=self.model_name,
        )
