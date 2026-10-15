import os
import logging
from app.core.config import settings
from app.llm_gateway.base import BaseLLMAdapter
from app.llm_gateway.mock_adapter import DeterministicMockAdapter
from app.llm_gateway.openai_adapter import OpenAIAdapter
from app.llm_gateway.gemini_adapter import GeminiAdapter

logger = logging.getLogger("llm_gateway.factory")


def _fallback_to_gemini(model_name: str) -> BaseLLMAdapter:
    logger.warning("Provider cho '%s' chưa được cấu hình API key trong ENV. Tự động fallback về 'gemini:gemini-2.5-flash'.", model_name)
    gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if gemini_key:
        return GeminiAdapter(model_name="gemini-2.5-flash", api_key=gemini_key)
    return DeterministicMockAdapter(model_name="gemini-2.5-flash")


def get_llm_adapter(model_name: str = "mock-math-solver") -> BaseLLMAdapter:
    """Returns the appropriate LLM adapter based on the requested model name.
    Supports independent providers: Gemini, Alibaba Cloud MaaS, DeepSeek Native, DeepInfra, and OpenRouter.
    Automatically falls back to Gemini if a provider API key is not configured in ENV.
    """
    name = model_name.lower()

    if name.startswith("mock") or model_name == "mock-math-council":
        return DeterministicMockAdapter(model_name=model_name)

    # 1. Alibaba Cloud Model Studio (MaaS)
    elif name.startswith("alibaba:") or name.startswith("alibaba"):
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        alibaba_key = os.getenv("ALIBABA_API_KEY", getattr(settings, "ALIBABA_API_KEY", ""))
        alibaba_base = os.getenv(
            "ALIBABA_BASE_URL",
            getattr(
                settings,
                "ALIBABA_BASE_URL",
                "https://ws-dgcpkbso457jl8mu.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
            ),
        ).rstrip("/")
        if alibaba_key:
            return OpenAIAdapter(
                model_name=actual_model,
                api_key=alibaba_key,
                api_base=alibaba_base,
            )
        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)
        return _fallback_to_gemini(model_name)

    # 2. DeepSeek Native
    elif name.startswith("deepseek:") or name.startswith("deepseek"):
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", ""))
        deepseek_base = os.getenv(
            "DEEPSEEK_BASE_URL", getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        ).rstrip("/")
        if deepseek_key:
            return OpenAIAdapter(
                model_name=actual_model,
                api_key=deepseek_key,
                api_base=deepseek_base,
            )
        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)
        return _fallback_to_gemini(model_name)

    # 3. DeepInfra
    elif name.startswith("deepinfra:") or name.startswith("deepinfra"):
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        deepinfra_key = os.getenv("DEEPINFRA_API_KEY", getattr(settings, "DEEPINFRA_API_KEY", ""))
        deepinfra_base = os.getenv(
            "DEEPINFRA_BASE_URL",
            getattr(settings, "DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai"),
        ).rstrip("/")
        if deepinfra_key:
            return OpenAIAdapter(
                model_name=actual_model,
                api_key=deepinfra_key,
                api_base=deepinfra_base,
            )
        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)
        return _fallback_to_gemini(model_name)

    # 4. Google Gemini
    elif name.startswith("gemini") or "google" in name:
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            return GeminiAdapter(model_name=actual_model, api_key=gemini_key)
        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)
        raise ValueError(
            f"Chưa cấu hình API Key cho Gemini ('{model_name}'). "
            "Vui lòng thiết lập biến môi trường GEMINI_API_KEY trên Railway Variables."
        )

    # Optional Native OpenAI
    elif name.startswith("openai:") or name.startswith("gpt") or name.startswith("o1") or name.startswith("o3"):
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if openai_key:
            return OpenAIAdapter(model_name=actual_model, api_key=openai_key)
        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)
        raise ValueError(
            f"Chưa cấu hình API Key cho OpenAI ('{model_name}'). "
            "Vui lòng thiết lập biến môi trường OPENAI_API_KEY trên Railway Variables."
        )

    # Optional Native Anthropic
    elif name.startswith("anthropic:") or name.startswith("claude"):
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        anthropic_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            from app.llm_gateway.base_and_adapters import AnthropicAdapter
            return AnthropicAdapter()
        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)
        raise ValueError(
            f"Chưa cấu hình API Key cho Anthropic Claude ('{model_name}'). "
            "Vui lòng thiết lập biến môi trường ANTHROPIC_API_KEY trên Railway Variables."
        )

    elif settings.DEFAULT_LLM_PROVIDER == "mock":
        return DeterministicMockAdapter(model_name=model_name)

    else:
        logger.error(
            "CRITICAL: get_llm_adapter cannot resolve model '%s' while DEFAULT_LLM_PROVIDER is '%s'. "
            "Silent fallback to DeterministicMockAdapter is strictly forbidden in live mode.",
            model_name,
            settings.DEFAULT_LLM_PROVIDER,
        )
        raise ValueError(
            f"Không thể khởi tạo adapter cho model '{model_name}' ở chế độ live. "
            f"Tuyệt đối cấm fallback ngầm về Mock Adapter khi gặp lỗi hoặc cấu hình sai."
        )
