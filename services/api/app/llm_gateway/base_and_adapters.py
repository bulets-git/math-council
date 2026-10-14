import abc
import json
import re
import time
from decimal import Decimal
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel
from app.core.config import settings
from app.schemas.agent_contracts import (
    ChallengeAdjudicationItemSchema,
    ChallengeItemSchema,
    ClaimItemSchema,
    JudgeOutputSchema,
    NormalizationOutputSchema,
    ProofStepSchema,
    SkepticOutputSchema,
    SolverOutputSchema,
    SolverRevisionOutputSchema,
    SourceDiscoveryOutputSchema,
    SourceMetadataSchema,
)

T = TypeVar("T", bound=BaseModel)

MODEL_PRICING_PER_1M: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-2.5-flash": (Decimal("0.15"), Decimal("0.60")),
    "gemini-2.5-pro": (Decimal("1.25"), Decimal("5.00")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "o3-mini": (Decimal("1.10"), Decimal("4.40")),
    "claude-3-7-sonnet-latest": (Decimal("3.00"), Decimal("15.00")),
    "deepseek-chat": (Decimal("0.27"), Decimal("1.10")),
    "deepseek-reasoner": (Decimal("0.55"), Decimal("2.19")),
}


def calculate_call_cost(model_name: str, input_tokens: int, output_tokens: int) -> Decimal:
    in_price, out_price = MODEL_PRICING_PER_1M.get(
        model_name, (Decimal("1.00"), Decimal("3.00"))
    )
    cost = (Decimal(input_tokens) * in_price + Decimal(output_tokens) * out_price) / Decimal("1000000")
    return cost.quantize(Decimal("0.000001"))


def extract_json_object(raw_text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace : last_brace + 1]
    return cleaned


def build_schema_instruction(system_prompt: str, response_schema: type[BaseModel]) -> str:
    schema_json = json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
    return (
        f"{system_prompt}\n\n"
        "BẮT BUỘC: Chỉ trả về một đối tượng JSON hợp lệ duy nhất tuân thủ JSON Schema sau:\n"
        f"{schema_json}"
    )


class LLMCallResult(BaseModel):
    parsed_data: dict[str, Any]
    provider: str
    model_name: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_ms: int
    provider_request_id: str | None = None


class BaseLLMAdapter(abc.ABC):
    provider_name: str = "base"

    @abc.abstractmethod
    async def generate_structured(
        self,
        *,
        model_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        raise NotImplementedError


class OpenAIAdapter(BaseLLMAdapter):
    provider_name = "openai"

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url.rstrip("/")

    async def generate_structured(
        self,
        *,
        model_name: str = "gpt-4o",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        if not self.api_key:
            raise RuntimeError(f"Thiếu API Key cho provider '{self.provider_name}'.")

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_content = data["choices"][0]["message"]["content"]
        validated = response_schema.model_validate_json(extract_json_object(raw_content))

        usage = data.get("usage", {})
        in_tok = int(usage.get("prompt_tokens", 0))
        out_tok = int(usage.get("completion_tokens", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
            provider_request_id=data.get("id"),
        )


class OpenAICompatibleAdapter(OpenAIAdapter):
    provider_name = "openai_compatible"

    def __init__(self) -> None:
        super().__init__(
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            base_url=settings.OPENAI_COMPATIBLE_BASE_URL,
        )


class AnthropicAdapter(BaseLLMAdapter):
    provider_name = "anthropic"

    async def generate_structured(
        self,
        *,
        model_name: str = "claude-3-7-sonnet-latest",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("Thiếu ANTHROPIC_API_KEY trong biến môi trường.")

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        payload = {
            "model": model_name,
            "max_tokens": 4096,
            "temperature": 0.2,
            "system": full_system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_text = data["content"][0]["text"]
        validated = response_schema.model_validate_json(extract_json_object(raw_text))

        usage = data.get("usage", {})
        in_tok = int(usage.get("input_tokens", 0))
        out_tok = int(usage.get("output_tokens", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
            provider_request_id=data.get("id"),
        )


class GeminiAdapter(BaseLLMAdapter):
    provider_name = "gemini"

    async def generate_structured(
        self,
        *,
        model_name: str = "gemini-2.5-pro",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("Thiếu GEMINI_API_KEY trong biến môi trường.")

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": full_system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(url, params={"key": settings.GEMINI_API_KEY}, json=payload)
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        validated = response_schema.model_validate_json(extract_json_object(raw_text))

        usage = data.get("usageMetadata", {})
        in_tok = int(usage.get("promptTokenCount", 0))
        out_tok = int(usage.get("candidatesTokenCount", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
        )


class DeterministicMockAdapter(BaseLLMAdapter):
    provider_name = "mock"

    async def generate_structured(
        self,
        *,
        model_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 60.0,
    ) -> tuple[T, LLMCallResult]:
        start = time.perf_counter()

        if response_schema is NormalizationOutputSchema:
            needs_review = r"a^2 + b^2 + c^2 \le 1" in user_prompt or "NEEDS_REVIEW" in user_prompt
            obj = NormalizationOutputSchema(
                statement_normalized=user_prompt.strip(),
                needs_clarification=needs_review,
                clarification_reason=(
                    "Đề bài có dấu hiệu chép sai chiều bất đẳng thức: với a=b=c=1 thì a^2+b^2+c^2 = 3 > 1."
                    if needs_review
                    else None
                ),
                detected_subject="Toán Olympic",
            )
        elif response_schema is SolverOutputSchema:
            obj = SolverOutputSchema(
                task_type="solve",
                status="completed",
                summary="Biến đổi tương đương và sử dụng tính chất chia hết / bất đẳng thức cổ điển.",
                claims=[
                    ClaimItemSchema(
                        claim_id="C1",
                        statement="Thiết lập đẳng thức cơ sở hoặc điều kiện biên của bài toán.",
                        reasoning="Biến đổi đại số trực tiếp từ giả thiết đề bài.",
                        depends_on=[],
                        status="unverified",
                    ),
                    ClaimItemSchema(
                        claim_id="C2",
                        statement="Suy ra kết luận của bài toán từ mệnh đề C1.",
                        reasoning="Kết hợp C1 và tính chất số nguyên / bất đẳng thức.",
                        depends_on=["C1"],
                        status="unverified",
                    ),
                ],
                proof_steps=[
                    ProofStepSchema(step_id="S1", claim_refs=["C1"], content="Bước 1: Thiết lập bổ đề C1."),
                    ProofStepSchema(step_id="S2", claim_refs=["C1", "C2"], content="Bước 2: Hoàn tất chứng minh C2."),
                ],
                unresolved_questions=[],
                confidence="high",
            )
        elif response_schema is SkepticOutputSchema:
            if "21n + 4" in user_prompt:
                obj = SkepticOutputSchema(
                    overall_assessment="Lời giải chặt chẽ, tổ hợp tuyến tính đúng.",
                    challenges=[],
                    confidence="high",
                )
            else:
                obj = SkepticOutputSchema(
                    overall_assessment="Cần làm rõ điều kiện biên ở bước suy luận C2.",
                    challenges=[
                        ChallengeItemSchema(
                            target_claim_id="C2",
                            error_type="missing_case",
                            severity="major",
                            explanation="Chưa kiểm tra trường hợp biên khi mẫu số hoặc nhân tử triệt tiêu bằng 0.",
                            counterexample="Thử với giá trị biên x = y hoặc n = 1.",
                            required_fix="Bổ sung xét riêng trường hợp suy biến trước khi chia.",
                        )
                    ],
                    confidence="high",
                )
        elif response_schema is SolverRevisionOutputSchema:
            revised = SolverOutputSchema(
                task_type="revise",
                status="completed",
                summary="Đã bổ sung xét trường hợp biên theo phản biện của Skeptic.",
                claims=[
                    ClaimItemSchema(
                        claim_id="C1",
                        statement="Xét trường hợp biên suy biến, đẳng thức luôn thỏa mãn.",
                        reasoning="Thay trực tiếp giá trị biên vào phương trình gốc.",
                        depends_on=[],
                        status="supported",
                    ),
                    ClaimItemSchema(
                        claim_id="C2",
                        statement="Với trường hợp khác 0, thực hiện phép biến đổi tương đương suy ra ĐPCM.",
                        reasoning="Vì đã loại trừ trường hợp bằng 0 ở C1 nên phép chia hoàn toàn hợp lệ.",
                        depends_on=["C1"],
                        status="supported",
                    ),
                ],
                proof_steps=[
                    ProofStepSchema(step_id="S1", claim_refs=["C1", "C2"], content="Chứng minh đầy đủ cả 2 trường hợp.")
                ],
                confidence="high",
            )
            obj = SolverRevisionOutputSchema(
                revised_solution=revised,
                challenge_responses=[
                    {
                        "target_claim_id": "C2",
                        "action": "revised",
                        "response_explanation": "Đã tách trường hợp mẫu bằng 0 thành mệnh đề C1 riêng biệt.",
                    }
                ],
            )
        elif response_schema is JudgeOutputSchema:
            obj = JudgeOutputSchema(
                verdict_status="supported",
                selected_solver_role="solver_a",
                summary="Lời giải sau khi chỉnh sửa đã lấp đầy lỗ hổng xét trường hợp biên.",
                final_proof_markdown="### Lời giải tổng hợp\n1. Xét trường hợp biên (Mệnh đề C1).\n2. Xét trường hợp tổng quát (Mệnh đề C2).",
                challenge_adjudications=[
                    ChallengeAdjudicationItemSchema(
                        target_claim_id="C2",
                        new_status="accepted",
                        reason="Solver đã bổ sung mệnh đề C1 giải quyết triệt để trường hợp chia cho 0.",
                    )
                ],
                accepted_claims=["C1", "C2"],
                unresolved_issues=[],
            )
        elif response_schema is SourceDiscoveryOutputSchema:
            if "21n + 4" in user_prompt and "14n + 3" in user_prompt:
                canonical = SolverOutputSchema(
                    summary="Chứng minh phân số tối giản bằng thuật toán Euclid và tổ hợp tuyến tính triệt tiêu n.",
                    claims=[
                        ClaimItemSchema(
                            claim_id="C1",
                            statement="Gọi d = gcd(21n + 4, 14n + 3) với d là số nguyên dương.",
                            reasoning="Định nghĩa ước chung lớn nhất của tử số và mẫu số.",
                            depends_on=[],
                            status="supported",
                        ),
                        ClaimItemSchema(
                            claim_id="C2",
                            statement="Ta có d chia hết cho 2(21n + 4) - 3(14n + 3) = 42n + 8 - 42n - 9 = -1.",
                            reasoning="Tính chất tổ hợp tuyến tính triệt tiêu biến n: d | (2A - 3B).",
                            depends_on=["C1"],
                            status="supported",
                        ),
                        ClaimItemSchema(
                            claim_id="C3",
                            statement="Vì d | 1 và d > 0 nên d = 1. Phân số (21n + 4)/(14n + 3) tối giản với mọi số tự nhiên n.",
                            reasoning="Ước chung lớn nhất bằng 1 nên tử và mẫu nguyên tố cùng nhau.",
                            depends_on=["C2"],
                            status="supported",
                        ),
                    ],
                    proof_steps=[
                        ProofStepSchema(step_id="S1", claim_refs=["C1"], content="Đặt d = (21n + 4, 14n + 3)."),
                        ProofStepSchema(step_id="S2", claim_refs=["C2"], content="Xét 2(21n + 4) - 3(14n + 3) = -1 chia hết cho d."),
                        ProofStepSchema(step_id="S3", claim_refs=["C3"], content="Suy ra d = 1, phân số tối giản (đpcm)."),
                    ],
                    unresolved_questions=[],
                    confidence="high",
                )
                obj = SourceDiscoveryOutputSchema(
                    match_type="exact_match",
                    source_found=True,
                    source_metadata=SourceMetadataSchema(
                        competition_name="International Mathematical Olympiad (IMO)",
                        year=1959,
                        problem_number="Problem 1",
                        reference_urls=["https://artofproblemsolving.com/community/c6h54829"],
                    ),
                    variant_warning=None,
                    canonical_solution=canonical,
                )
            elif "21n" in user_prompt or "14n" in user_prompt:
                obj = SourceDiscoveryOutputSchema(
                    match_type="modified_variant",
                    source_found=True,
                    source_metadata=SourceMetadataSchema(
                        competition_name="International Mathematical Olympiad (IMO)",
                        year=1959,
                        problem_number="Problem 1 (Variant)",
                        reference_urls=["https://artofproblemsolving.com/community/c6h54829"],
                    ),
                    variant_warning="Đề bài có cấu trúc tương tự IMO 1959 Problem 1 nhưng các hệ số đã bị thay đổi.",
                    canonical_solution=None,
                )
            else:
                obj = SourceDiscoveryOutputSchema(
                    match_type="no_match",
                    source_found=False,
                    source_metadata=None,
                    variant_warning=None,
                    canonical_solution=None,
                )
        else:
            raise ValueError(f"Unsupported schema in MockAdapter: {response_schema}")

        elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
        validated = response_schema.model_validate(obj.model_dump())
        meta = LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=250,
            output_tokens=180,
            cost_usd=Decimal("0.001500"),
            latency_ms=elapsed_ms,
            provider_request_id="mock-req-001",
        )
        return validated, meta


class MultiProviderRouter:
    def __init__(self, force_mock: bool = False) -> None:
        self.force_mock = force_mock or (settings.DEFAULT_LLM_PROVIDER == "mock")
        self.adapters: dict[str, BaseLLMAdapter] = {
            "mock": DeterministicMockAdapter(),
            "gemini": GeminiAdapter(),
            "openai": OpenAIAdapter(),
            "anthropic": AnthropicAdapter(),
            "openai_compatible": OpenAICompatibleAdapter(),
        }

    def resolve_spec(self, role_model_spec: str) -> tuple[BaseLLMAdapter, str]:
        if self.force_mock or role_model_spec.startswith("mock:"):
            model_part = role_model_spec.split(":", 1)[1] if ":" in role_model_spec else role_model_spec
            return self.adapters["mock"], model_part

        if ":" in role_model_spec:
            provider_key, model_name = role_model_spec.split(":", 1)
        else:
            provider_key, model_name = settings.DEFAULT_LLM_PROVIDER, role_model_spec

        adapter = self.adapters.get(provider_key)
        if not adapter:
            raise ValueError(f"Provider '{provider_key}' không được hỗ trợ. Hỗ trợ: {list(self.adapters.keys())}")
        return adapter, model_name

    async def call_for_role(
        self,
        *,
        role_model_spec: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        adapter, model_name = self.resolve_spec(role_model_spec)
        return await adapter.generate_structured(
            model_name=model_name,
            prompt_version=prompt_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            timeout_sec=timeout_sec,
        )


def get_available_models_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "gemini:gemini-2.5-pro",
            "provider": "gemini",
            "model_name": "gemini-2.5-pro",
            "configured": bool(settings.GEMINI_API_KEY),
            "recommended_roles": ["solver_a", "solver_b", "judge"],
        },
        {
            "id": "openai:gpt-4o",
            "provider": "openai",
            "model_name": "gpt-4o",
            "configured": bool(settings.OPENAI_API_KEY),
            "recommended_roles": ["solver_a", "solver_b", "judge"],
        },
        {
            "id": "openai:o3-mini",
            "provider": "openai",
            "model_name": "o3-mini",
            "configured": bool(settings.OPENAI_API_KEY),
            "recommended_roles": ["solver_a", "solver_b", "skeptic"],
        },
        {
            "id": "anthropic:claude-3-7-sonnet-latest",
            "provider": "anthropic",
            "model_name": "claude-3-7-sonnet-latest",
            "configured": bool(settings.ANTHROPIC_API_KEY),
            "recommended_roles": ["skeptic", "solver_b", "judge"],
        },
        {
            "id": "openai_compatible:deepseek-reasoner",
            "provider": "openai_compatible",
            "model_name": "deepseek-reasoner",
            "configured": bool(settings.OPENAI_COMPATIBLE_API_KEY),
            "recommended_roles": ["solver_a", "solver_c", "skeptic"],
        },
        {
            "id": "openai_compatible:google/gemini-2.5-flash:online",
            "provider": "openai_compatible",
            "model_name": "google/gemini-2.5-flash:online",
            "configured": bool(settings.OPENAI_COMPATIBLE_API_KEY),
            "recommended_roles": ["source_finder"],
        },
        {
            "id": "mock:deterministic-olympiad-v1",
            "provider": "mock",
            "model_name": "deterministic-olympiad-v1",
            "configured": True,
            "recommended_roles": ["normalizer", "source_finder", "solver_a", "solver_b", "skeptic", "judge"],
        },
    ]
