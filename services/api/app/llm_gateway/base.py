from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Type
from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    parsed_json: dict[str, Any] | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Decimal = Decimal("0.000000")
    latency_ms: int = 0
    model_name: str


class BaseLLMAdapter(ABC):
    def __init__(self, model_name: str, api_key: str | None = None):
        self.model_name = model_name
        self.api_key = api_key

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generates response from LLM provider."""
        pass
