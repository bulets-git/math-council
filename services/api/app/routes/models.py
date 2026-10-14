from fastapi import APIRouter
from app.llm_gateway.base_and_adapters import get_available_models_catalog
from app.schemas.step3_schemas import ModelInfoResponse

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelInfoResponse], summary="Danh sách LLM models được cấu hình")
async def list_models() -> list[ModelInfoResponse]:
    catalog = get_available_models_catalog()
    models: list[ModelInfoResponse] = [
        ModelInfoResponse(
            id="mock-math-council",
            name="Deterministic Mock Council (Default)",
            provider="mock",
            context_window=128000,
            is_default=True,
        )
    ]
    for item in catalog:
        models.append(
            ModelInfoResponse(
                id=item["id"],
                name=f"{item['provider'].upper()}: {item['model_name']}",
                provider=item["provider"],
                context_window=1000000 if "pro" in item["model_name"] or "sonnet" in item["model_name"] else 128000,
                is_default=(item["id"] == "mock:deterministic-olympiad-v1"),
            )
        )
    return models
