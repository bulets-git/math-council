import logging
from app.core.config import settings
from app.llm_gateway.base import BaseLLMAdapter
from app.llm_gateway.mock_adapter import DeterministicMockAdapter
from app.llm_gateway.openai_adapter import OpenAIAdapter
from app.llm_gateway.gemini_adapter import GeminiAdapter

logger = logging.getLogger("llm_gateway.factory")


def get_llm_adapter(model_name: str = "mock-math-solver") -> BaseLLMAdapter:
    """Returns the appropriate LLM adapter based on the requested model name.
    Strictly forbids silent fallback to DeterministicMockAdapter when DEFAULT_LLM_PROVIDER == 'live'.
    """
    name = model_name.lower()
    if name.startswith("mock") or model_name == "mock-math-council":
        return DeterministicMockAdapter(model_name=model_name)
    elif name.startswith("openai_compatible:") or name.startswith("openrouter:") or "openai_compatible" in name:
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        return OpenAIAdapter(
            model_name=actual_model,
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            api_base=settings.OPENAI_COMPATIBLE_BASE_URL,
        )
    elif name.startswith("gpt") or name.startswith("o1") or name.startswith("o3") or "openai" in name:
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        return OpenAIAdapter(model_name=actual_model)
    elif name.startswith("gemini") or "google" in name:
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        return GeminiAdapter(model_name=actual_model)
    elif name.startswith("claude") or "anthropic" in name:
        from app.llm_gateway.base_and_adapters import AnthropicAdapter
        actual_model = model_name.split(":", 1)[1] if ":" in model_name else model_name
        return AnthropicAdapter()
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
