from app.llm_gateway.base import BaseLLMAdapter
from app.llm_gateway.mock_adapter import DeterministicMockAdapter
from app.llm_gateway.openai_adapter import OpenAIAdapter
from app.llm_gateway.gemini_adapter import GeminiAdapter


def get_llm_adapter(model_name: str = "mock-math-solver") -> BaseLLMAdapter:
    """Returns the appropriate LLM adapter based on the requested model name."""
    name = model_name.lower()
    if name.startswith("gpt") or name.startswith("o1") or name.startswith("o3") or "openai" in name:
        return OpenAIAdapter(model_name=model_name)
    elif name.startswith("gemini") or "google" in name:
        return GeminiAdapter(model_name=model_name)
    else:
        # Default fallback to DeterministicMockAdapter
        return DeterministicMockAdapter(model_name=model_name)
