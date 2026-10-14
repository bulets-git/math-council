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

    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: str | None = None):
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
                "Vui lòng thiết lập biến môi trường GEMINI_API_KEY trên Railway Variables."
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

        if kwargs.get("tools"):
            payload["tools"] = kwargs["tools"]
        elif kwargs.get("grounding"):
            payload["tools"] = [{"google_search": {}}]

        if response_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        timeout_sec = kwargs.get("timeout_sec", 60.0)
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
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

    async def generate_with_grounding(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout_sec: float = 12.0,
    ) -> dict[str, Any]:
        """Tra cứu với công cụ Google Search Grounding qua Google GenAI SDK hoặc REST API."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình.")

        summary = ""
        reference_urls: list[str] = []
        raw_grounding: dict[str, Any] = {}

        sdk_success = False
        try:
            import asyncio
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            cfg = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[{"google_search": {}}],
                temperature=0.2,
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt,
                    config=cfg,
                ),
                timeout=timeout_sec,
            )
            if response.candidates:
                cand = response.candidates[0]
                if cand.content and cand.content.parts:
                    summary = "".join([p.text for p in cand.content.parts if getattr(p, "text", None)]).strip()
                elif hasattr(response, "text") and response.text:
                    summary = (response.text or "").strip()

                gm = getattr(cand, "grounding_metadata", None)
                if gm:
                    chunks = getattr(gm, "grounding_chunks", None) or []
                    for chunk in chunks:
                        web = getattr(chunk, "web", None)
                        if web:
                            uri = getattr(web, "uri", None)
                            if uri and uri not in reference_urls:
                                reference_urls.append(uri)
                    try:
                        raw_grounding = gm.model_dump() if hasattr(gm, "model_dump") else {}
                    except Exception:
                        pass
            elif hasattr(response, "text") and response.text:
                summary = response.text.strip()
            sdk_success = True
        except asyncio.TimeoutError:
            raise
        except Exception:
            pass

        if not sdk_success:
            url = f"{self.api_base}/models/{self.model_name}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": user_prompt}]}],
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.2},
            }
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            candidates = data.get("candidates", [])
            if candidates:
                cand = candidates[0]
                parts = cand.get("content", {}).get("parts", [])
                summary = "".join([p.get("text", "") for p in parts]).strip()
                gm = cand.get("groundingMetadata", {})
                raw_grounding = gm
                for chunk in gm.get("groundingChunks", []):
                    web = chunk.get("web", {})
                    uri = web.get("uri")
                    if uri and uri not in reference_urls:
                        reference_urls.append(uri)

        return {
            "summary": summary,
            "reference_urls": reference_urls,
            "grounding_metadata": raw_grounding,
        }
