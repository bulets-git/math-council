import json
import time
from decimal import Decimal
from typing import Any, Type
from pydantic import BaseModel

from app.llm_gateway.base import BaseLLMAdapter, LLMResponse
from app.schemas.agent_contracts import (
    ChallengeItem,
    ClaimItem,
    JudgeOutput,
    NormalizerOutput,
    SkepticOutput,
    SolverOutput,
)


class DeterministicMockAdapter(BaseLLMAdapter):
    """Deterministic Mock Adapter for testing without external API calls or costs."""

    def __init__(self, model_name: str = "mock-math-solver"):
        super().__init__(model_name=model_name, api_key="mock-key")

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        start_time = time.perf_counter()

        parsed: dict[str, Any] = {}

        if response_schema is NormalizerOutput or (response_schema is None and "Chuyên gia Chuẩn hóa" in system_prompt):
            clean_stmt = user_prompt.strip()
            if "<untrusted_user_input>" in clean_stmt and "</untrusted_user_input>" in clean_stmt:
                clean_stmt = clean_stmt.split("<untrusted_user_input>")[1].split("</untrusted_user_input>")[0].strip()
            elif "<problem_statement>" in clean_stmt and "</problem_statement>" in clean_stmt:
                clean_stmt = clean_stmt.split("<problem_statement>")[1].split("</problem_statement>")[0].strip()
            if not clean_stmt:
                clean_stmt = "Cho phương trình $ax^2 + bx + c = 0$ ($a \\neq 0$)."

            obj = NormalizerOutput(
                normalized_statement=clean_stmt,
                assumptions=["$a, b, c \\in \\mathbb{R}$", "$a \\neq 0$"],
                extracted_variables={"a": "hệ số bậc 2", "b": "hệ số bậc 1", "c": "hệ số tự do"},
                has_ambiguity=False,
                ambiguity_warning=None,
            )
            parsed = obj.model_dump()
        elif response_schema is SkepticOutput or (response_schema is None and "Nhà Phản Biện" in system_prompt):
            obj = SkepticOutput(
                challenges=[
                    ChallengeItem(
                        target_claim_label="C2",
                        error_type="missing_case",
                        argument="Cần xét rõ điều kiện $\\Delta \\ge 0$ trước khi khai căn số thực ở bước C3.",
                    )
                ]
            )
            parsed = obj.model_dump()
        elif response_schema is JudgeOutput or (response_schema is None and "Thẩm Định Viên" in system_prompt):
            obj = JudgeOutput(
                consensus_status="consensus_reached",
                winning_solver="solver_a",
                final_latex_solution="Phương trình có nghiệm: $$x = \\frac{-b \\pm \\sqrt{\\Delta}}{2a}$$ với $\\Delta = b^2 - 4ac \\ge 0$.",
                executive_summary="Hội đồng đã xem xét và thống nhất bổ sung điều kiện căn thức từ phản biện của Skeptic.",
                confidence_score=0.98,
                dissenting_opinions=[],
            )
            parsed = obj.model_dump()
        elif response_schema is SolverOutput or (response_schema is None and ("Chuyên gia Giải toán" in system_prompt or "Reviser" in system_prompt)):
            obj = SolverOutput(
                summary="Sử dụng phương pháp biệt thức Delta để tìm nghiệm.",
                claims=[
                    ClaimItem(label="C1", content="Xét biệt thức $\\Delta = b^2 - 4ac$.", claim_type="definition", depends_on=[]),
                    ClaimItem(label="C2", content="Biến đổi thành $(x + \\frac{b}{2a})^2 = \\frac{\\Delta}{4a^2}$.", claim_type="inference", depends_on=["C1"]),
                    ClaimItem(label="C3", content="Khai căn hai vế được nghiệm $x_{1,2} = \\frac{-b \\pm \\sqrt{\\Delta}}{2a}$.", claim_type="calculation", depends_on=["C2"]),
                ],
                final_answer="x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}",
            )
            parsed = obj.model_dump()
        else:
            parsed = {"status": "success", "echo": user_prompt[:100]}

        content = json.dumps(parsed, ensure_ascii=False)
        latency_ms = int((time.perf_counter() - start_time) * 1000) or 5
        prompt_tokens = len(system_prompt.split()) + len(user_prompt.split())
        completion_tokens = len(content.split())

        # Cost simulation: $0.0015 per 1k tokens
        cost = Decimal(str(round((prompt_tokens + completion_tokens) * 0.0000015, 6)))

        return LLMResponse(
            content=content,
            parsed_json=parsed,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            model_name=self.model_name,
        )
