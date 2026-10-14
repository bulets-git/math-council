import logging
import os
from typing import Any, TypeVar
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
    MultiProviderRouter,
    get_available_models_catalog,
)

logger = logging.getLogger("llm_gateway.router")

__all__ = [
    "MultiProviderRouter",
    "AlibabaAdapter",
    "DeepInfraAdapter",
    "OpenAICompatibleAdapter",
    "get_available_models_catalog",
]
