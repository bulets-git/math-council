"""
Bộ máy Điều phối Hội đồng Giải toán (Math Council State Machine Orchestrator).
Đã tích hợp trực tiếp MultiProviderRouter: Mỗi vai trò (Normalizer, Source Finder, Solver A, Solver B, Skeptic, Judge)
có thể chạy trên một hãng AI khác nhau và tự động ghi nhận tổng chi phí USD.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Any, Awaitable, Callable

logger = logging.getLogger("orchestrator.council_runner")
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
    SourceMetadataSchema,
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
            "retriever": settings.ROLE_RETRIEVER_MODEL,
            "source_finder": settings.ROLE_RETRIEVER_MODEL,
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
            role_hint="normalizer",
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

        # 1.5. RETRIEVING_SOURCE (Tìm kiếm Nguồn gốc Đề toán với Google Search Grounding)
        source_disc_out: SourceDiscoveryOutputSchema | None = None
        retriever_model = (
            self.role_models.get("retriever")
            or self.role_models.get("source_finder")
            or getattr(settings, "ROLE_RETRIEVER_MODEL", "gemini:gemini-2.5-flash")
        )
        if getattr(settings, "ENABLE_SOURCE_DISCOVERY", True) and retriever_model:
            await self._emit("retrieving_source", {"model": retriever_model})
            try:
                retriever_prompt = (
                    f"Hãy tra cứu trên Internet xuất xứ và nguồn gốc của bài toán sau: kỳ thi nào (IMO, VMO, Putnam, HSG, v.v.), "
                    f"năm tổ chức, bài số mấy, nguồn đăng tải (AoPS, diễn đàn toán học). "
                    f"Tóm tắt xuất xứ, đề bài gốc và lời giải chuẩn ngắn gọn nếu có.\n\n"
                    f"Đề bài cần tra cứu:\n{problem_text}"
                )
                grounding_res, src_meta = await asyncio.wait_for(
                    self.router.retrieve_source_with_grounding(
                        role_model_spec=retriever_model,
                        system_prompt=(
                            "Bạn là trợ lý tra cứu nguồn gốc và xuất xứ đề thi toán học học thuật bằng công cụ Google Search Grounding. "
                            "Hãy tìm kiếm chính xác bài toán trên Internet, trích xuất kỳ thi, năm tổ chức, bài số mấy và tóm tắt nguồn gốc."
                        ),
                        user_prompt=retriever_prompt,
                        timeout_sec=12.0,
                    ),
                    timeout=12.0,
                )
                if src_meta:
                    self._record_call(src_meta)

                summary_text = (grounding_res.get("summary") or "").strip() if grounding_res else ""
                ref_urls = grounding_res.get("reference_urls", []) if grounding_res else []
                source_found = bool(summary_text and len(summary_text) > 10)

                source_disc_out = SourceDiscoveryOutputSchema(
                    match_type="exact_match" if (source_found and any(k in summary_text.upper() for k in ["IMO", "VMO", "PUTNAM", "USAMO"])) else ("modified_variant" if source_found else "no_match"),
                    source_found=source_found,
                    origin_summary=summary_text if source_found else None,
                    reference_urls=ref_urls,
                    source_metadata=SourceMetadataSchema(
                        competition_name="Internet Grounding Discovery",
                        reference_urls=ref_urls,
                    ) if source_found else None,
                    variant_warning=None,
                    canonical_solution=None,
                )

                await self._emit(
                    "retrieving_source",
                    {
                        "summary": summary_text,
                        "reference_urls": ref_urls,
                        "source_found": source_found,
                        "match_type": source_disc_out.match_type,
                    },
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Quá thời gian tìm kiếm nguồn đề (timeout > 12s) ở bước retrieving_source. Gán kết quả là None và lập tức chuyển trạng thái sang solving."
                )
                source_disc_out = None
            except Exception as e:
                logger.warning(
                    "Không thể tìm kiếm nguồn đề hoặc gặp lỗi ở bước retrieving_source (%s). Gán kết quả là None và lập tức chuyển trạng thái sang solving.",
                    e,
                )
                source_disc_out = None
        elif not retriever_model:
            logger.warning(
                "Công cụ tìm kiếm nguồn đề (ROLE_RETRIEVER_MODEL) không được cấu hình. Gán kết quả là None và chuyển thẳng sang solving."
            )
            source_disc_out = None

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
                role_hint="skeptic",
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
                role_hint="judge",
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
            if source_disc_out.origin_summary:
                reference_notes += f"\n[THÔNG TIN NGUỒN GỐC INTERNET]: {source_disc_out.origin_summary}"
            if source_disc_out.reference_urls:
                reference_notes += f"\n[LIÊN KẾT NGUỒN THAM KHẢO]: {', '.join(source_disc_out.reference_urls)}"
            sm = source_disc_out.source_metadata
            if sm and sm.competition_name and sm.competition_name != "Internet Grounding Discovery":
                reference_notes += f"\n[TÀI LIỆU NGUỒN THAM KHẢO]: Kỳ thi: {sm.competition_name}."
            if source_disc_out.variant_warning:
                reference_notes += f"\n[CẢNH BÁO BIẾN THỂ]: {source_disc_out.variant_warning}"
            if source_disc_out.canonical_solution:
                reference_notes += f"\n[TÓM TẮT LỜI GIẢI GỐC]: {source_disc_out.canonical_solution.summary}"

        # 2. SOLVING (Song song Solver A, Solver B và Solver C nếu được cấu hình)
        solver_roles = ["solver_a", "solver_b"]
        if self.role_models.get("solver_c"):
            solver_roles.append("solver_c")

        await self._emit(
            "solving",
            {role: self.role_models[role] for role in solver_roles},
        )
        solver_prompt_input = wrap_untrusted_content("normalized_problem", problem_text) + reference_notes

        solver_calls = await asyncio.gather(
            *[
                self.router.call_for_role(
                    role_model_spec=self.role_models[role],
                    prompt_version=SOLVER_PROMPT_V1.version,
                    system_prompt=SOLVER_PROMPT_V1.system_instruction + f"\nVai trò: {role.replace('_', ' ').title()}.",
                    user_prompt=solver_prompt_input,
                    response_schema=SolverOutputSchema,
                    role_hint=role,
                )
                for role in solver_roles
            ]
        )
        for _, meta_s in solver_calls:
            self._record_call(meta_s)

        current_solvers = {role: res[0] for role, res in zip(solver_roles, solver_calls)}
        dag_validations = {
            f"{role}_valid": validate_claims_dag(current_solvers[role].claims).is_valid
            for role in solver_roles
        }

        # 3 & 4. CRITIQUING & REVISING
        all_critiques: list[dict[str, Any]] = []

        for round_idx in range(1, max_rounds + 1):
            await self._emit("critiquing", {"round": round_idx, "skeptic": self.role_models["skeptic"]})
            crit_calls = await asyncio.gather(
                *[
                    self.router.call_for_role(
                        role_model_spec=self.role_models["skeptic"],
                        prompt_version=SKEPTIC_PROMPT_V1.version,
                        system_prompt=SKEPTIC_PROMPT_V1.system_instruction,
                        user_prompt=(
                            wrap_untrusted_content("problem", problem_text)
                            + "\n"
                            + wrap_untrusted_content(f"{role}_solution", current_solvers[role].model_dump_json())
                        ),
                        response_schema=SkepticOutputSchema,
                        role_hint="skeptic",
                    )
                    for role in solver_roles
                ]
            )
            for _, meta_c in crit_calls:
                self._record_call(meta_c)

            crit_map = {role: res[0] for role, res in zip(solver_roles, crit_calls)}
            round_crit: dict[str, Any] = {"round": round_idx}
            for role in solver_roles:
                round_crit[f"{role}_challenges"] = [c.model_dump() for c in crit_map[role].challenges]
            all_critiques.append(round_crit)

            if not any(bool(crit_map[role].challenges) for role in solver_roles):
                break

            await self._emit("revising", {"round": round_idx})
            for role in solver_roles:
                if crit_map[role].challenges:
                    rev_res, meta_r = await self.router.call_for_role(
                        role_model_spec=self.role_models[role],
                        prompt_version=REVISER_PROMPT_V1.version,
                        system_prompt=REVISER_PROMPT_V1.system_instruction,
                        user_prompt=(
                            wrap_untrusted_content("problem", problem_text)
                            + "\n"
                            + wrap_untrusted_content("previous_solution", current_solvers[role].model_dump_json())
                            + "\n"
                            + wrap_untrusted_content("skeptic_challenges", crit_map[role].model_dump_json())
                        ),
                        response_schema=SolverRevisionOutputSchema,
                        role_hint=f"{role}_revision",
                    )
                    self._record_call(meta_r)
                    current_solvers[role] = rev_res.revised_solution

        # 5. ADJUDICATING (Judge tổng hợp)
        await self._emit("adjudicating", {"judge": self.role_models["judge"]})
        solvers_final_str = "\n".join(
            wrap_untrusted_content(f"{role}_final", current_solvers[role].model_dump_json())
            for role in solver_roles
        )
        judge_input = (
            wrap_untrusted_content("problem", problem_text)
            + (f"\n[NGUỒN GỐC BÀI TOÁN]: {source_disc_out.source_metadata.competition_name}\n" if (source_disc_out and source_disc_out.source_found and source_disc_out.source_metadata) else "")
            + "\n"
            + solvers_final_str
            + "\n"
            + wrap_untrusted_content("critique_history", str(all_critiques))
        )
        judge_out, meta_j = await self.router.call_for_role(
            role_model_spec=self.role_models["judge"],
            prompt_version=JUDGE_PROMPT_V1.version,
            system_prompt=JUDGE_PROMPT_V1.system_instruction,
            user_prompt=judge_input,
            response_schema=JudgeOutputSchema,
            role_hint="judge",
        )
        self._record_call(meta_j)

        await self._emit("completed", {"verdict": judge_out.verdict_status})
        result_payload: dict[str, Any] = {
            "final_status": "completed",
            "normalization": norm_out.model_dump(),
            "discovered_source": source_disc_out.model_dump() if source_disc_out else None,
            "fast_track_applied": False,
            "dag_validation": dag_validations,
            "solver_a_final": current_solvers["solver_a"].model_dump(),
            "solver_b_final": current_solvers["solver_b"].model_dump(),
            "critiques": all_critiques,
            "judge_report": judge_out.model_dump(),
            "total_cost_usd": str(self.total_cost_usd),
            "model_calls": [c.model_dump() for c in self.call_history],
        }
        if "solver_c" in current_solvers:
            result_payload["solver_c_final"] = current_solvers["solver_c"].model_dump()
        return result_payload

    # Alias for convenience
    run = execute_pipeline


# Alias for compatibility
CouncilRunner = MathCouncilOrchestrator
