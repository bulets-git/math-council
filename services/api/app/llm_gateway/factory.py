import os
import logging
from app.core.config import settings
from app.llm_gateway.base import BaseLLMAdapter
from app.llm_gateway.mock_adapter import DeterministicMockAdapter
from app.llm_gateway.openai_adapter import OpenAIAdapter
from app.llm_gateway.gemini_adapter import GeminiAdapter

logger = logging.getLogger("llm_gateway.factory")


def get_llm_adapter(model_name: str = "mock-math-solver") -> BaseLLMAdapter:
    """Returns the appropriate LLM adapter based on the requested model name.
    Strictly forbids silent fallback to DeterministicMockAdapter when DEFAULT_LLM_PROVIDER == 'live' or mode == 'live'.
    Supports routing models through OpenRouter (OPENAI_COMPATIBLE) if individual provider keys are missing.
    """
    name = model_name.lower()
    openrouter_key = (
        settings.OPENAI_COMPATIBLE_API_KEY
        or os.getenv("OPENAI_COMPATIBLE_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
    )
    openrouter_base = settings.OPENAI_COMPATIBLE_BASE_URL or "https://openrouter.ai/api/v1"

    if name.startswith("mock") or model_name == "mock-math-council":
        return DeterministicMockAdapter(model_name=model_name)

    elif name.startswith("openai_compatible:") or name.startswith("openrouter:") or "openai_compatible" in name:
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        if not openrouter_key:
            if settings.DEFAULT_LLM_PROVIDER == "mock":
                return DeterministicMockAdapter(model_name=model_name)
            raise ValueError(
                "Chưa cấu hình OPENAI_COMPATIBLE_API_KEY hoặc OPENROUTER_API_KEY trên Railway Variables."
            )
        return OpenAIAdapter(
            model_name=actual_model,
            api_key=openrouter_key,
            api_base=openrouter_base,
        )

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

        if openrouter_key:
            openrouter_model = actual_model if actual_model.startswith("deepseek/") else f"deepseek/{actual_model}"
            logger.info("Routing DeepSeek model '%s' via OpenRouter as '%s'", actual_model, openrouter_model)
            return OpenAIAdapter(
                model_name=openrouter_model,
                api_key=openrouter_key,
                api_base=openrouter_base,
            )

        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)

        raise ValueError(
            f"Chưa cấu hình API Key cho DeepSeek ('{model_name}'). "
            "Vui lòng thiết lập biến môi trường DEEPSEEK_API_KEY hoặc OPENAI_COMPATIBLE_API_KEY (OpenRouter) trên Railway."
        )

    elif name.startswith("gemini") or "google" in name:
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            return GeminiAdapter(model_name=actual_model, api_key=gemini_key)
        
        # Transparent routing through OpenRouter if available
        if openrouter_key:
            openrouter_model = actual_model if actual_model.startswith("google/") else f"google/{actual_model}"
            logger.info("Routing Gemini model '%s' via OpenRouter as '%s'", actual_model, openrouter_model)
            return OpenAIAdapter(
                model_name=openrouter_model,
                api_key=openrouter_key,
                api_base=openrouter_base,
            )

        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)

        raise ValueError(
            f"Chưa cấu hình API Key cho Gemini ('{model_name}'). "
            "Vui lòng thiết lập biến môi trường GEMINI_API_KEY hoặc OPENAI_COMPATIBLE_API_KEY (OpenRouter) trên Railway."
        )

    elif name.startswith("gpt") or name.startswith("o1") or name.startswith("o3") or "openai" in name:
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if openai_key:
            return OpenAIAdapter(model_name=actual_model, api_key=openai_key)

        if openrouter_key:
            openrouter_model = actual_model if actual_model.startswith("openai/") else f"openai/{actual_model}"
            logger.info("Routing OpenAI model '%s' via OpenRouter as '%s'", actual_model, openrouter_model)
            return OpenAIAdapter(
                model_name=openrouter_model,
                api_key=openrouter_key,
                api_base=openrouter_base,
            )

        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)

        raise ValueError(
            f"Chưa cấu hình API Key cho OpenAI ('{model_name}'). "
            "Vui lòng thiết lập biến môi trường OPENAI_API_KEY hoặc OPENAI_COMPATIBLE_API_KEY (OpenRouter) trên Railway."
        )

    elif name.startswith("claude") or "anthropic" in name:
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        anthropic_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            from app.llm_gateway.base_and_adapters import AnthropicAdapter
            return AnthropicAdapter()

        if openrouter_key:
            openrouter_model = actual_model if actual_model.startswith("anthropic/") else f"anthropic/{actual_model}"
            logger.info("Routing Anthropic Claude model '%s' via OpenRouter as '%s'", actual_model, openrouter_model)
            return OpenAIAdapter(
                model_name=openrouter_model,
                api_key=openrouter_key,
                api_base=openrouter_base,
            )

        if settings.DEFAULT_LLM_PROVIDER == "mock":
            return DeterministicMockAdapter(model_name=model_name)

        raise ValueError(
            f"Chưa cấu hình API Key cho Anthropic Claude ('{model_name}'). "
            "Vui lòng thiết lập biến môi trường ANTHROPIC_API_KEY hoặc OPENAI_COMPATIBLE_API_KEY (OpenRouter) trên Railway."
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
