"""
Bộ máy Điều phối Hội đồng Giải toán (Math Council State Machine Orchestrator).
Đã tích hợp trực tiếp MultiProviderRouter: Mỗi vai trò (Normalizer, Source Finder, Solver A, Solver B, Skeptic, Judge)
có thể chạy trên một hãng AI khác nhau và tự động ghi nhận tổng chi phí USD.
"""
import asyncio
from decimal import Decimal
from typing import Any, Awaitable, Callable
from app.claims.dag_validator import validate_claims_dag
from app.core.config import settings
from app.llm_gateway.base_and_adapters import LLMCallResult, MultiProviderRouter
from app.prompts.math_council_prompts import (
    JUDGE_PROMPT_V1,
    NORMALIZER_PROMPT_V1,
    REVISER_PROMPT_V1,
    SKEPTIC_PROMPT_V1,
    SOLVER_PROMPT_V1,
    SOURCE_FINDER_PROMPT_V1,
    wrap_untrusted_content,
)
from app.schemas.agent_contracts import (
    JudgeOutputSchema,
    NormalizationOutputSchema,
    SkepticOutputSchema,
    SolverOutputSchema,
    SolverRevisionOutputSchema,
    SourceDiscoveryOutputSchema,
)


class MathCouncilOrchestrator:
    def __init__(
        self,
        router: MultiProviderRouter | None = None,
        role_models: dict[str, str] | None = None,
        on_stage_change: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
        fast_track_known_problems: bool = True,
    ) -> None:
        self.router = router or MultiProviderRouter()
        default_roles = {
            "normalizer": settings.ROLE_NORMALIZER_MODEL,
            "source_finder": settings.ROLE_SOURCE_FINDER_MODEL,
            "solver_a": settings.ROLE_SOLVER_A_MODEL,
            "solver_b": settings.ROLE_SOLVER_B_MODEL,
            "solver_c": settings.ROLE_SOLVER_C_MODEL,
            "skeptic": settings.ROLE_SKEPTIC_MODEL,
            "judge": settings.ROLE_JUDGE_MODEL,
        }
        if role_models:
            default_roles.update(role_models)
        self.role_models = default_roles
        self.on_stage_change = on_stage_change
        self.fast_track_known_problems = fast_track_known_problems
        self.call_history: list[LLMCallResult] = []
        self.total_cost_usd: Decimal = Decimal("0.000000")

    def _record_call(self, meta: LLMCallResult) -> None:
        self.call_history.append(meta)
        self.total_cost_usd += meta.cost_usd

    async def _emit(self, stage: str, payload: dict[str, Any]) -> None:
        if self.on_stage_change:
            await self.on_stage_change(stage, payload)

    async def execute_pipeline(
        self,
        statement_original: str,
        max_rounds: int = 2,
        fast_track_known_problems: bool | None = None,
    ) -> dict[str, Any]:
        if fast_track_known_problems is None:
            fast_track_known_problems = self.fast_track_known_problems
        # 1. NORMALIZING
        await self._emit("normalizing", {"model": self.role_models["normalizer"]})
        norm_out, norm_meta = await self.router.call_for_role(
            role_model_spec=self.role_models["normalizer"],
            prompt_version=NORMALIZER_PROMPT_V1.version,
            system_prompt=NORMALIZER_PROMPT_V1.system_instruction,
            user_prompt=wrap_untrusted_content("problem_statement", statement_original),
            response_schema=NormalizationOutputSchema,
        )
        self._record_call(norm_meta)

        if norm_out.needs_clarification:
            await self._emit(
                "needs_review",
                {"reason": norm_out.clarification_reason, "normalized": norm_out.statement_normalized},
            )
            return {
                "final_status": "needs_review",
                "normalization": norm_out.model_dump(),
                "total_cost_usd": str(self.total_cost_usd),
                "model_calls": [c.model_dump() for c in self.call_history],
            }

        problem_text = norm_out.statement_normalized

        # 1.5. RETRIEVING_SOURCE (Tìm kiếm Nguồn gốc Đề toán)
        source_disc_out: SourceDiscoveryOutputSchema | None = None
        if getattr(settings, "ENABLE_SOURCE_DISCOVERY", True):
            await self._emit("retrieving_source", {"model": self.role_models["source_finder"]})
            src_out, src_meta = await self.router.call_for_role(
                role_model_spec=self.role_models["source_finder"],
                prompt_version=SOURCE_FINDER_PROMPT_V1.version,
                system_prompt=SOURCE_FINDER_PROMPT_V1.system_instruction,
                user_prompt=wrap_untrusted_content("problem_statement", problem_text),
                response_schema=SourceDiscoveryOutputSchema,
            )
            self._record_call(src_meta)
            source_disc_out = src_out
            await self._emit(
                "retrieving_source",
                {
                    "match_type": src_out.match_type,
                    "source_found": src_out.source_found,
                    "source_metadata": src_out.source_metadata.model_dump() if src_out.source_metadata else None,
                    "variant_warning": src_out.variant_warning,
                },
            )

        # TRƯỜNG HỢP 1: exact_match và có canonical_solution -> Fast-track nếu được bật
        if (
            source_disc_out
            and source_disc_out.match_type == "exact_match"
            and source_disc_out.canonical_solution
            and fast_track_known_problems
        ):
            canonical = source_disc_out.canonical_solution
            dag_res = validate_claims_dag(canonical.claims)

            # Skeptic thẩm định lời giải chuẩn (1 lượt để kiểm tra dịch thuật / giả thiết)
            await self._emit(
                "critiquing",
                {"round": 1, "skeptic": self.role_models["skeptic"], "fast_track": True},
            )
            crit_out, meta_crit = await self.router.call_for_role(
                role_model_spec=self.role_models["skeptic"],
                prompt_version=SKEPTIC_PROMPT_V1.version,
                system_prompt=SKEPTIC_PROMPT_V1.system_instruction + "\n(Thẩm định Lời giải chuẩn từ nguồn gốc kỳ thi).",
                user_prompt=(
                    wrap_untrusted_content("problem", problem_text)
                    + "\n"
                    + wrap_untrusted_content("canonical_solution", canonical.model_dump_json())
                ),
                response_schema=SkepticOutputSchema,
            )
            self._record_call(meta_crit)

            critiques = [{
                "round": 1,
                "solver_a_challenges": [c.model_dump() for c in crit_out.challenges],
                "solver_b_challenges": [],
            }]

            # Chuyển thẳng tới Judge để xuất báo cáo cuối gồm Nguồn gốc + Lời giải chuẩn
            await self._emit("adjudicating", {"judge": self.role_models["judge"], "fast_track": True})
            source_desc = ""
            if source_disc_out.source_metadata:
                sm = source_disc_out.source_metadata
                source_desc = f"Kỳ thi: {sm.competition_name}, Năm: {sm.year}, Bài: {sm.problem_number}. Tham khảo: {', '.join(sm.reference_urls)}"

            judge_input = (
                wrap_untrusted_content("problem", problem_text)
                + f"\n[NGUỒN GỐC ĐỀ TOÁN]: {source_desc}\n"
                + wrap_untrusted_content("canonical_solution", canonical.model_dump_json())
                + "\n"
                + wrap_untrusted_content("critique_result", crit_out.model_dump_json())
            )
            judge_out, meta_j = await self.router.call_for_role(
                role_model_spec=self.role_models["judge"],
                prompt_version=JUDGE_PROMPT_V1.version,
                system_prompt=JUDGE_PROMPT_V1.system_instruction + f"\nThông tin nguồn gốc: {source_desc}",
                user_prompt=judge_input,
                response_schema=JudgeOutputSchema,
            )
            self._record_call(meta_j)

            await self._emit("completed", {"verdict": judge_out.verdict_status, "fast_track": True})
            return {
                "final_status": "completed",
                "normalization": norm_out.model_dump(),
                "discovered_source": source_disc_out.model_dump(),
                "fast_track_applied": True,
                "dag_validation": {"solver_a_valid": dag_res.is_valid, "solver_b_valid": dag_res.is_valid},
                "solver_a_final": canonical.model_dump(),
                "solver_b_final": canonical.model_dump(),
                "critiques": critiques,
                "judge_report": judge_out.model_dump(),
                "total_cost_usd": str(self.total_cost_usd),
                "model_calls": [c.model_dump() for c in self.call_history],
            }

        # TRƯỜNG HỢP 2 & 3: modified_variant hoặc no_match hoặc không bật fast-track
        reference_notes = ""
        if source_disc_out and source_disc_out.source_found:
            sm = source_disc_out.source_metadata
            reference_notes += f"\n[TÀI LIỆU NGUỒN THAM KHẢO]: Kỳ thi: {sm.competition_name if sm else 'N/A'}."
            if source_disc_out.variant_warning:
                reference_notes += f"\n[CẢNH BÁO BIẾN THỂ]: {source_disc_out.variant_warning}"
            if source_disc_out.canonical_solution:
                reference_notes += f"\n[TÓM TẮT LỜI GIẢI GỐC]: {source_disc_out.canonical_solution.summary}"

        # 2. SOLVING (Song song Solver A và Solver B trên 2 model độc lập)
        await self._emit(
            "solving",
            {"solver_a": self.role_models["solver_a"], "solver_b": self.role_models["solver_b"]},
        )
        solver_prompt_input = wrap_untrusted_content("normalized_problem", problem_text) + reference_notes

        (solver_a_out, meta_a), (solver_b_out, meta_b) = await asyncio.gather(
            self.router.call_for_role(
                role_model_spec=self.role_models["solver_a"],
                prompt_version=SOLVER_PROMPT_V1.version,
                system_prompt=SOLVER_PROMPT_V1.system_instruction + "\nVai trò: Solver A.",
                user_prompt=solver_prompt_input,
                response_schema=SolverOutputSchema,
            ),
            self.router.call_for_role(
                role_model_spec=self.role_models["solver_b"],
                prompt_version=SOLVER_PROMPT_V1.version,
                system_prompt=SOLVER_PROMPT_V1.system_instruction + "\nVai trò: Solver B.",
                user_prompt=solver_prompt_input,
                response_schema=SolverOutputSchema,
            ),
        )
        self._record_call(meta_a)
        self._record_call(meta_b)

        dag_a = validate_claims_dag(solver_a_out.claims)
        dag_b = validate_claims_dag(solver_b_out.claims)

        # 3 & 4. CRITIQUING & REVISING
        current_a = solver_a_out
        current_b = solver_b_out
        all_critiques: list[dict[str, Any]] = []

        for round_idx in range(1, max_rounds + 1):
            await self._emit("critiquing", {"round": round_idx, "skeptic": self.role_models["skeptic"]})
            (crit_a, meta_ca), (crit_b, meta_cb) = await asyncio.gather(
                self.router.call_for_role(
                    role_model_spec=self.role_models["skeptic"],
                    prompt_version=SKEPTIC_PROMPT_V1.version,
                    system_prompt=SKEPTIC_PROMPT_V1.system_instruction,
                    user_prompt=(
                        wrap_untrusted_content("problem", problem_text)
                        + "\n"
                        + wrap_untrusted_content("solver_a_solution", current_a.model_dump_json())
                    ),
                    response_schema=SkepticOutputSchema,
                ),
                self.router.call_for_role(
                    role_model_spec=self.role_models["skeptic"],
                    prompt_version=SKEPTIC_PROMPT_V1.version,
                    system_prompt=SKEPTIC_PROMPT_V1.system_instruction,
                    user_prompt=(
                        wrap_untrusted_content("problem", problem_text)
                        + "\n"
                        + wrap_untrusted_content("solver_b_solution", current_b.model_dump_json())
                    ),
                    response_schema=SkepticOutputSchema,
                ),
            )
            self._record_call(meta_ca)
            self._record_call(meta_cb)

            all_critiques.append({
                "round": round_idx,
                "solver_a_challenges": [c.model_dump() for c in crit_a.challenges],
                "solver_b_challenges": [c.model_dump() for c in crit_b.challenges],
            })

            if not crit_a.challenges and not crit_b.challenges:
                break

            await self._emit("revising", {"round": round_idx})
            if crit_a.challenges:
                rev_a, meta_ra = await self.router.call_for_role(
                    role_model_spec=self.role_models["solver_a"],
                    prompt_version=REVISER_PROMPT_V1.version,
                    system_prompt=REVISER_PROMPT_V1.system_instruction,
                    user_prompt=(
                        wrap_untrusted_content("problem", problem_text)
                        + "\n"
                        + wrap_untrusted_content("previous_solution", current_a.model_dump_json())
                        + "\n"
                        + wrap_untrusted_content("skeptic_challenges", crit_a.model_dump_json())
                    ),
                    response_schema=SolverRevisionOutputSchema,
                )
                self._record_call(meta_ra)
                current_a = rev_a.revised_solution

            if crit_b.challenges:
                rev_b, meta_rb = await self.router.call_for_role(
                    role_model_spec=self.role_models["solver_b"],
                    prompt_version=REVISER_PROMPT_V1.version,
                    system_prompt=REVISER_PROMPT_V1.system_instruction,
                    user_prompt=(
                        wrap_untrusted_content("problem", problem_text)
                        + "\n"
                        + wrap_untrusted_content("previous_solution", current_b.model_dump_json())
                        + "\n"
                        + wrap_untrusted_content("skeptic_challenges", crit_b.model_dump_json())
                    ),
                    response_schema=SolverRevisionOutputSchema,
                )
                self._record_call(meta_rb)
                current_b = rev_b.revised_solution

        # 5. ADJUDICATING (Judge tổng hợp)
        await self._emit("adjudicating", {"judge": self.role_models["judge"]})
        judge_input = (
            wrap_untrusted_content("problem", problem_text)
            + (f"\n[NGUỒN GỐC BÀI TOÁN]: {source_disc_out.source_metadata.competition_name}\n" if (source_disc_out and source_disc_out.source_found and source_disc_out.source_metadata) else "")
            + "\n"
            + wrap_untrusted_content("solver_a_final", current_a.model_dump_json())
            + "\n"
            + wrap_untrusted_content("solver_b_final", current_b.model_dump_json())
            + "\n"
            + wrap_untrusted_content("critique_history", str(all_critiques))
        )
        judge_out, meta_j = await self.router.call_for_role(
            role_model_spec=self.role_models["judge"],
            prompt_version=JUDGE_PROMPT_V1.version,
            system_prompt=JUDGE_PROMPT_V1.system_instruction,
            user_prompt=judge_input,
            response_schema=JudgeOutputSchema,
        )
        self._record_call(meta_j)

        await self._emit("completed", {"verdict": judge_out.verdict_status})
        return {
            "final_status": "completed",
            "normalization": norm_out.model_dump(),
            "discovered_source": source_disc_out.model_dump() if source_disc_out else None,
            "fast_track_applied": False,
            "dag_validation": {"solver_a_valid": dag_a.is_valid, "solver_b_valid": dag_b.is_valid},
            "solver_a_final": current_a.model_dump(),
            "solver_b_final": current_b.model_dump(),
            "critiques": all_critiques,
            "judge_report": judge_out.model_dump(),
            "total_cost_usd": str(self.total_cost_usd),
            "model_calls": [c.model_dump() for c in self.call_history],
        }

    # Alias for convenience
    run = execute_pipeline


# Alias for compatibility
CouncilRunner = MathCouncilOrchestrator
