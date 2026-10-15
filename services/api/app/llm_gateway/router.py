"""
Universal Provider Registry & MultiProviderRouter
Cung cấp:
1. Universal Provider Registry đọc động cấu hình ENV (gemini, deepseek, alibaba, deepinfra, openrouter).
   Nếu provider chưa có API key trong ENV, tự động fallback về 'gemini:gemini-2.5-flash'.
2. Auto-Fallback on Failure (Graceful Degradation):
   Khi gọi LLM gặp lỗi 402 (Payment Required), 429 (Rate Limit), Timeout, hoặc lỗi API nhà mạng,
   tự động bắt exception, ghi log cảnh báo và gọi mô hình dự phòng (gemini:gemini-2.5-flash hoặc gemini:gemini-2.5-pro)
   để hoàn thành bước, tuyệt đối không làm gãy State Machine của Hội đồng.
"""
import asyncio
import logging
import os
from typing import Any, TypeVar
from decimal import Decimal

from pydantic import BaseModel

from app.core.config import settings
from app.llm_gateway.base_and_adapters import (
    BaseLLMAdapter,
    LLMCallResult,
    DeterministicMockAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    AnthropicAdapter,
    OpenAICompatibleAdapter,
    AlibabaAdapter,
    DeepInfraAdapter,
    OpenRouterAdapter,
)

logger = logging.getLogger("llm_gateway.router")

T = TypeVar("T", bound=BaseModel)


class UniversalProviderRegistry:
    """
    Universal Provider Registry: Đọc động cấu hình các nhà cung cấp (gemini, deepseek, alibaba, deepinfra, openrouter).
    Nếu một provider chưa có API key trong ENV, không văng lỗi sập ứng dụng mà tự động fallback về gemini:gemini-2.5-flash.
    """

    def __init__(self) -> None:
        pass

    def get_configured_providers(self) -> dict[str, bool]:
        """Kiểm tra sự tồn tại của API Key cho từng nhà cung cấp từ ENV động."""
        return {
            "gemini": bool(settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")),
            "deepseek": bool(os.getenv("DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", ""))),
            "alibaba": bool(os.getenv("ALIBABA_API_KEY", getattr(settings, "ALIBABA_API_KEY", ""))),
            "deepinfra": bool(os.getenv("DEEPINFRA_API_KEY", getattr(settings, "DEEPINFRA_API_KEY", ""))),
            "openrouter": bool(
                os.getenv("OPENROUTER_API_KEY")
                or os.getenv("OPENAI_COMPATIBLE_API_KEY")
                or getattr(settings, "OPENROUTER_API_KEY", "")
            ),
        }

    def resolve_adapter(
        self,
        role_model_spec: str,
        force_mock: bool = False,
    ) -> tuple[BaseLLMAdapter, str]:
        """
        Phân giải role_model_spec thành (adapter, model_name).
        Nếu thiếu API Key trong ENV, tự động fallback về 'gemini:gemini-2.5-flash' thay vì văng lỗi.
        """
        if force_mock or role_model_spec.startswith("mock:"):
            model_part = role_model_spec.split(":", 1)[1] if ":" in role_model_spec else role_model_spec
            return DeterministicMockAdapter(), model_part

        if ":" in role_model_spec:
            provider_key, model_name = role_model_spec.split(":", 1)
        else:
            provider_key, model_name = settings.DEFAULT_LLM_PROVIDER, role_model_spec

        provider_key = provider_key.lower().strip()

        # 1. Google Gemini
        if provider_key == "gemini":
            gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                if settings.DEFAULT_LLM_PROVIDER == "mock" or force_mock:
                    return DeterministicMockAdapter(), model_name
                logger.warning(
                    "⚠️ [REGISTRY] GEMINI_API_KEY chưa được cấu hình. Sử dụng DeterministicMockAdapter tạm thời để bảo toàn ứng dụng."
                )
                return DeterministicMockAdapter(), model_name
            return GeminiAdapter(model_name=model_name), model_name

        # 2. DeepSeek Native
        if provider_key == "deepseek":
            deepseek_key = os.getenv("DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", ""))
            if not deepseek_key:
                logger.warning(
                    "⚠️ [REGISTRY] Provider 'deepseek' (model '%s') chưa có DEEPSEEK_API_KEY trong ENV. Tự động fallback về 'gemini:gemini-2.5-flash'.",
                    model_name,
                )
                return self.resolve_adapter("gemini:gemini-2.5-flash", force_mock=force_mock)
            deepseek_base = os.getenv(
                "DEEPSEEK_BASE_URL", getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            ).rstrip("/")
            adapter = OpenAIAdapter(api_key=deepseek_key, base_url=deepseek_base)
            adapter.provider_name = "deepseek"
            return adapter, model_name

        # 3. Alibaba Cloud MaaS
        if provider_key == "alibaba":
            alibaba_key = os.getenv("ALIBABA_API_KEY", getattr(settings, "ALIBABA_API_KEY", ""))
            if not alibaba_key:
                logger.warning(
                    "⚠️ [REGISTRY] Provider 'alibaba' (model '%s') chưa có ALIBABA_API_KEY trong ENV. Tự động fallback về 'gemini:gemini-2.5-flash'.",
                    model_name,
                )
                return self.resolve_adapter("gemini:gemini-2.5-flash", force_mock=force_mock)
            alibaba_base = os.getenv(
                "ALIBABA_BASE_URL",
                getattr(
                    settings,
                    "ALIBABA_BASE_URL",
                    "https://ws-dgcpkbso457jl8mu.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
                ),
            ).rstrip("/")
            return AlibabaAdapter(api_key=alibaba_key, base_url=alibaba_base), model_name

        # 4. DeepInfra
        if provider_key == "deepinfra":
            deepinfra_key = os.getenv("DEEPINFRA_API_KEY", getattr(settings, "DEEPINFRA_API_KEY", ""))
            if not deepinfra_key:
                logger.warning(
                    "⚠️ [REGISTRY] Provider 'deepinfra' (model '%s') chưa có DEEPINFRA_API_KEY trong ENV. Tự động fallback về 'gemini:gemini-2.5-flash'.",
                    model_name,
                )
                return self.resolve_adapter("gemini:gemini-2.5-flash", force_mock=force_mock)
            deepinfra_base = os.getenv(
                "DEEPINFRA_BASE_URL",
                getattr(settings, "DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai"),
            ).rstrip("/")
            return DeepInfraAdapter(api_key=deepinfra_key, base_url=deepinfra_base), model_name

        # 5. OpenRouter
        if provider_key in ("openrouter", "openai_compatible"):
            openrouter_key = (
                os.getenv("OPENROUTER_API_KEY")
                or os.getenv("OPENAI_COMPATIBLE_API_KEY")
                or getattr(settings, "OPENROUTER_API_KEY", "")
            )
            if not openrouter_key:
                logger.warning(
                    "⚠️ [REGISTRY] Provider 'openrouter' (model '%s') chưa có OPENROUTER_API_KEY trong ENV. Tự động fallback về 'gemini:gemini-2.5-flash'.",
                    model_name,
                )
                return self.resolve_adapter("gemini:gemini-2.5-flash", force_mock=force_mock)
            openrouter_base = (
                os.getenv("OPENROUTER_BASE_URL")
                or getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            ).rstrip("/")
            return OpenRouterAdapter(api_key=openrouter_key, base_url=openrouter_base), model_name

        # Unknown provider fallback
        logger.warning(
            "⚠️ [REGISTRY] Provider '%s' (spec: '%s') không có trong registry. Tự động fallback về 'gemini:gemini-2.5-flash'.",
            provider_key,
            role_model_spec,
        )
        return self.resolve_adapter("gemini:gemini-2.5-flash", force_mock=force_mock)


class MultiProviderRouter:
    """
    Bộ định tuyến đa nhà cung cấp với:
    - Universal Provider Registry đọc động cấu hình.
    - Graceful Degradation / Auto-Fallback on Failure:
      Khi gặp lỗi 402 Payment Required, 429 Rate Limit, Timeout, hoặc lỗi API bên thứ 3,
      tự động chuyển hướng gọi mô hình dự phòng (gemini:gemini-2.5-flash hoặc gemini:gemini-2.5-pro)
      để đảm bảo không bao giờ làm gãy State Machine của Hội đồng.
    """

    def __init__(self, force_mock: bool | None = None) -> None:
        self.registry = UniversalProviderRegistry()
        if force_mock is not None:
            self.force_mock = force_mock
        else:
            self.force_mock = (settings.DEFAULT_LLM_PROVIDER == "mock")

    def resolve_spec(self, role_model_spec: str) -> tuple[BaseLLMAdapter, str]:
        return self.registry.resolve_adapter(role_model_spec, force_mock=self.force_mock)

    async def call_for_role(
        self,
        *,
        role_model_spec: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
        role_hint: str = "",
    ) -> tuple[T, LLMCallResult]:
        """
        Gọi LLM theo vai trò với cơ chế Auto-Fallback on Failure (Graceful Degradation).
        """
        adapter, model_name = self.resolve_spec(role_model_spec)
        try:
            return await adapter.generate_structured(
                model_name=model_name,
                prompt_version=prompt_version,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=response_schema,
                timeout_sec=timeout_sec,
            )
        except Exception as primary_err:
            # Bắt 402 Payment Required (hết tiền), 429 Rate Limit, Timeout, hoặc lỗi API kết nối
            status_code = getattr(getattr(primary_err, "response", None), "status_code", None)
            logger.warning(
                "⚠️ [AUTO-FALLBACK] Lỗi khi gọi model '%s' cho vai trò '%s' (status=%s, error=%s). "
                "Kích hoạt cơ chế Graceful Degradation...",
                role_model_spec,
                role_hint or role_model_spec,
                status_code or "N/A",
                primary_err,
            )

            # Chọn mô hình dự phòng:
            # Judge và Skeptic cần khả năng phân tích sâu -> fallback gemini:gemini-2.5-pro
            # Solvers, Normalizer -> fallback gemini:gemini-2.5-flash
            is_high_reasoning = (
                role_hint.lower() in ("judge", "skeptic")
                or "pro" in role_model_spec.lower()
                or "reasoner" in role_model_spec.lower()
            )

            if is_high_reasoning:
                fallback_spec = (
                    "gemini:gemini-2.5-pro"
                    if "gemini-2.5-pro" not in role_model_spec
                    else "gemini:gemini-2.5-flash"
                )
            else:
                fallback_spec = (
                    "gemini:gemini-2.5-flash"
                    if "gemini-2.5-flash" not in role_model_spec
                    else "gemini:gemini-2.5-pro"
                )

            logger.warning(
                "🔄 [AUTO-FALLBACK] Đang chuyển tiếp thực thi sang mô hình dự phòng '%s' để giữ vững State Machine...",
                fallback_spec,
            )

            try:
                fallback_adapter, fallback_model = self.resolve_spec(fallback_spec)
                res, meta = await fallback_adapter.generate_structured(
                    model_name=fallback_model,
                    prompt_version=prompt_version,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    timeout_sec=timeout_sec,
                )
                meta.model_name = f"{fallback_model} (auto-fallback from {role_model_spec})"
                return res, meta
            except Exception as fb_err:
                logger.error(
                    "❌ [AUTO-FALLBACK-FAILED] Mô hình dự phòng '%s' cũng gặp lỗi (%s). "
                    "Chuyển sang Deterministic Mock Adapter để hoàn thành bước.",
                    fallback_spec,
                    fb_err,
                )
                mock_adapter = DeterministicMockAdapter()
                mock_model = "deterministic-olympiad-v1"
                return await mock_adapter.generate_structured(
                    model_name=mock_model,
                    prompt_version=prompt_version,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    timeout_sec=10.0,
                )

    async def retrieve_source_with_grounding(
        self,
        *,
        role_model_spec: str,
        system_prompt: str,
        user_prompt: str,
        timeout_sec: float = 12.0,
    ) -> tuple[dict[str, Any], LLMCallResult]:
        """
        Tra cứu xuất xứ đề toán với Google Search Grounding và tự động fallback nếu gặp lỗi.
        """
        adapter, model_name = self.resolve_spec(role_model_spec)
        try:
            if hasattr(adapter, "generate_with_grounding"):
                return await adapter.generate_with_grounding(
                    model_name=model_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    timeout_sec=timeout_sec,
                )
        except Exception as e:
            logger.warning(
                "⚠️ [GROUNDING-FALLBACK] Lỗi khi tra cứu với '%s' (%s). Thử lại với 'gemini:gemini-2.5-flash'...",
                role_model_spec,
                e,
            )

        # Fallback sang gemini:gemini-2.5-flash
        try:
            fb_adapter, fb_model = self.resolve_spec("gemini:gemini-2.5-flash")
            if hasattr(fb_adapter, "generate_with_grounding"):
                return await fb_adapter.generate_with_grounding(
                    model_name=fb_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    timeout_sec=timeout_sec,
                )
        except Exception as fb_err:
            logger.warning(
                "⚠️ [GROUNDING-FALLBACK] Cả fallback grounding cũng gặp lỗi (%s). Sử dụng mock grounding.",
                fb_err,
            )

        mock_adapter, _ = self.resolve_spec("mock:deterministic-olympiad-v1")
        return await mock_adapter.generate_with_grounding(
            model_name="mock",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_sec=5.0,
        )


__all__ = [
    "UniversalProviderRegistry",
    "MultiProviderRouter",
    "AlibabaAdapter",
    "DeepInfraAdapter",
    "OpenAICompatibleAdapter",
    "OpenRouterAdapter",
]
