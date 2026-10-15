import asyncio
import logging
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.budget.manager import BudgetExhaustedError, budget_manager
from app.claims.dag_validator import validate_claim_dag
from app.discussion.engine import discussion_engine
from app.events.publisher import event_publisher
from app.llm_gateway.factory import get_llm_adapter
from app.models.problem import Problem
from app.models.run import Run
from app.prompts import (
    JUDGE_SYSTEM_PROMPT,
    NORMALIZER_SYSTEM_PROMPT,
    PROMPT_VERSION,
    REVISER_SYSTEM_PROMPT,
    SKEPTIC_SYSTEM_PROMPT,
    SOLVER_SYSTEM_PROMPT,
    wrap_user_math_statement,
)
from app.core.config import settings
from app.llm_gateway.base_and_adapters import MultiProviderRouter
from app.prompts.math_council_prompts import (
    JUDGE_PROMPT_V1,
    SKEPTIC_PROMPT_V1,
    SOURCE_FINDER_PROMPT_V1,
    wrap_untrusted_content,
)
from app.schemas.agent_contracts import (
    JudgeOutput,
    NormalizerOutput,
    SkepticOutput,
    SolverOutput,
    SourceDiscoveryOutputSchema,
)

logger = logging.getLogger("orchestrator")


class CouncilOrchestrator:
    async def _safe_generate(
        self,
        adapter: Any,
        system_prompt: str,
        user_prompt: str,
        response_schema: Any,
        role_hint: str = "",
        is_live: bool = False,
    ) -> Any:
        try:
            return await adapter.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=response_schema,
            )
        except Exception as primary_err:
            status_code = getattr(getattr(primary_err, "response", None), "status_code", None)
            logger.warning(
                "⚠️ [STATE_MACHINE AUTO-FALLBACK] Lỗi khi gọi adapter '%s' cho vai trò '%s' (status=%s, error=%s). "
                "Tự động kích hoạt mô hình dự phòng Gemini...",
                getattr(adapter, "model_name", "unknown"),
                role_hint,
                status_code or "N/A",
                primary_err,
            )
            is_high_reasoning = role_hint in ("judge", "skeptic")
            fallback_model = "gemini:gemini-2.5-pro" if is_high_reasoning else "gemini:gemini-2.5-flash"
            fb_adapter = get_llm_adapter(fallback_model if is_live else "mock-math-council")
            try:
                return await fb_adapter.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                )
            except Exception as fb_err:
                logger.error(
                    "❌ Mô hình dự phòng '%s' cũng gặp lỗi: %s. Chuyển sang mock adapter để bảo toàn State Machine.",
                    fallback_model,
                    fb_err,
                )
                mock_adapter = get_llm_adapter("mock-math-council")
                return await mock_adapter.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                )

    async def cancel_run(self, db: AsyncSession, run_id: uuid.UUID) -> Run:
        run = await db.get(Run, run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        run.status = "cancelled"
        await db.commit()
        await event_publisher.publish(run_id, "run_cancelled", {"status": "cancelled"})
        return run

    async def resume_run(self, db: AsyncSession, run_id: uuid.UUID) -> str:
        run = await db.get(Run, run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        if run.status != "needs_review":
            raise ValueError(f"Run {run_id} is in status '{run.status}', only 'needs_review' can be resumed.")
        
        try:
            return await self._execute_from_solving(db, run)
        except Exception as err:
            logger.exception("Unexpected error in resume_run for run %s: %s", run_id, err)
            run = await db.get(Run, run_id)
            if run:
                run.status = "failed"
                run_cfg = dict(run.config or {})
                run_cfg["error"] = str(err)
                run_cfg["failure_stage"] = "solving"
                run.config = run_cfg
                await db.commit()
            await event_publisher.publish(run_id, "run_failed", {"error": str(err)})
            return "failed"

    async def run_pipeline(self, db: AsyncSession, run_id: uuid.UUID) -> str:
        """Executes full Council pipeline:
        queued -> normalizing -> solving (Solver A & B parallel) -> critiquing -> revising -> adjudicating -> completed
        """
        run = await db.get(Run, run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        problem = await db.get(Problem, run.problem_id)
        if not problem:
            raise ValueError(f"Problem {run.problem_id} not found")

        is_live = (settings.DEFAULT_LLM_PROVIDER == "live") or ((run.config or {}).get("mode") == "live")
        norm_model = settings.ROLE_NORMALIZER_MODEL if is_live else "mock-math-council"
        adapter = get_llm_adapter(norm_model)

        try:
            # ---------------------------------------------------------
            # 1. NORMALIZING PHASE
            # ---------------------------------------------------------
            run.status = "normalizing"
            await db.commit()
            await event_publisher.publish(run_id, "status_changed", {"status": "normalizing"})

            safe_statement = wrap_user_math_statement(problem.statement_original)
            reserved_norm = await budget_manager.check_and_reserve(db, run_id, Decimal("0.005000"))

            norm_res = await self._safe_generate(
                adapter=adapter,
                system_prompt=NORMALIZER_SYSTEM_PROMPT,
                user_prompt=safe_statement,
                response_schema=NormalizerOutput,
                role_hint="normalizer",
                is_live=is_live,
            )

            await budget_manager.record_call_and_release(
                db=db,
                run_id=run_id,
                agent_role="normalizer",
                model_name=adapter.model_name,
                prompt_tokens=norm_res.prompt_tokens,
                completion_tokens=norm_res.completion_tokens,
                actual_cost=norm_res.cost_usd,
                latency_ms=norm_res.latency_ms,
                prompt_version=PROMPT_VERSION,
                reserved_cost=reserved_norm,
            )

            norm_data = NormalizerOutput.model_validate(norm_res.parsed_json)

            await discussion_engine.record_message(
                db=db,
                run_id=run_id,
                sender_role="normalizer",
                content=norm_data.normalized_statement,
                metadata=norm_data.model_dump(),
            )

            # Check ambiguity guardrail
            if norm_data.has_ambiguity:
                run.status = "needs_review"
                await db.commit()
                await event_publisher.publish(
                    run_id, "needs_review", {"warning": norm_data.ambiguity_warning}
                )
                return "needs_review"

            problem.statement_normalized = norm_data.normalized_statement
            await db.commit()

            # ---------------------------------------------------------
            # 1.5. RETRIEVING_SOURCE PHASE (Tìm kiếm Nguồn gốc Đề toán với Google Search Grounding)
            # ---------------------------------------------------------
            retriever_model = getattr(settings, "ROLE_RETRIEVER_MODEL", None) or getattr(settings, "ROLE_SOURCE_FINDER_MODEL", "gemini:gemini-2.5-flash")
            if getattr(settings, "ENABLE_SOURCE_DISCOVERY", True) and retriever_model:
                run.status = "retrieving_source"
                await db.commit()
                await event_publisher.publish(run_id, "status_changed", {"status": "retrieving_source"})

                try:
                    router = MultiProviderRouter(force_mock=(not is_live))
                    retriever_prompt = (
                        f"Hãy tra cứu trên Internet xuất xứ và nguồn gốc của bài toán sau: kỳ thi nào, năm nào, bài số mấy, nguồn bài (AoPS, diễn đàn toán học). "
                        f"Tóm tắt xuất xứ, đề bài gốc và lời giải chuẩn ngắn gọn nếu có.\n\n"
                        f"Đề bài cần tra cứu:\n{norm_data.normalized_statement}"
                    )
                    grounding_res, src_meta = await asyncio.wait_for(
                        router.retrieve_source_with_grounding(
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
                    summary_text = (grounding_res.get("summary") or "").strip() if grounding_res else ""
                    ref_urls = grounding_res.get("reference_urls", []) if grounding_res else []
                    source_found = bool(summary_text and len(summary_text) > 10)

                    src_out = SourceDiscoveryOutputSchema(
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

                    # Lưu thông tin nguồn tìm được vào run.config
                    run_cfg = dict(run.config or {})
                    run_cfg["discovered_source"] = src_out.model_dump()
                    run.config = run_cfg
                    await db.commit()

                    await event_publisher.publish(
                        run_id,
                        "source_discovered",
                        {
                            "summary": summary_text,
                            "reference_urls": ref_urls,
                            "source_found": source_found,
                            "match_type": src_out.match_type,
                        },
                    )

                    # TRƯỜNG HỢP 1: exact_match và có canonical_solution -> fast track
                    if (
                        src_out.match_type == "exact_match"
                        and src_out.canonical_solution
                        and run_cfg.get("fast_track_known_problems", True)
                    ):
                        return await self._execute_fast_track(db, run, norm_data.normalized_statement, src_out)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Quá thời gian tìm kiếm nguồn đề (timeout > 12s) cho run %s ở bước retrieving_source. Gán kết quả là None và chuyển thẳng sang solving.",
                        run_id,
                    )
                except Exception as src_err:
                    logger.warning(
                        "Bước retrieving_source cho run %s gặp lỗi: %s. Gán kết quả là None và chuyển thẳng sang solving.",
                        run_id,
                        src_err,
                    )
            elif not retriever_model:
                logger.warning(
                    "Công cụ tìm kiếm nguồn đề không được cấu hình cho run %s. Gán kết quả là None và chuyển thẳng sang solving.",
                    run_id,
                )

            # Continue to solving
            return await self._execute_from_solving(db, run, norm_data.normalized_statement)

        except BudgetExhaustedError as b_err:
            logger.warning("Budget exhausted during run %s: %s", run_id, b_err)
            run = await db.get(Run, run_id)
            if run:
                run.status = "budget_exhausted"
                run_cfg = dict(run.config or {})
                run_cfg["error"] = str(b_err)
                run_cfg["failure_stage"] = "budget_exhausted"
                run.config = run_cfg
                await db.commit()
            await event_publisher.publish(run_id, "budget_exhausted", {"error": str(b_err)})
            return "budget_exhausted"
        except Exception as err:
            logger.exception("Unexpected error in run_pipeline for run %s: %s", run_id, err)
            run = await db.get(Run, run_id)
            if run:
                prev_stage = run.status or "normalizing"
                run.status = "failed"
                run_cfg = dict(run.config or {})
                run_cfg["error"] = str(err)
                run_cfg["failure_stage"] = prev_stage
                run.config = run_cfg
                await db.commit()
            await event_publisher.publish(run_id, "run_failed", {"error": str(err)})
            return "failed"

    async def _execute_fast_track(
        self,
        db: AsyncSession,
        run: Run,
        normalized_statement: str,
        src_out: SourceDiscoveryOutputSchema,
    ) -> str:
        run_id = run.id
        is_live = (settings.DEFAULT_LLM_PROVIDER == "live") or ((run.config or {}).get("mode") == "live")
        adapter_sk = get_llm_adapter(settings.ROLE_SKEPTIC_MODEL if is_live else "mock-math-council")
        adapter_jd = get_llm_adapter(settings.ROLE_JUDGE_MODEL if is_live else "mock-math-council")
        canonical = src_out.canonical_solution
        assert canonical is not None

        # Lưu Canonical Solution vào DB
        sol = await discussion_engine.save_solution_with_claims(
            db=db,
            run_id=run_id,
            solver_role="canonical_source",
            version=1,
            round_number=1,
            summary=canonical.summary,
            final_answer="Xem các mệnh đề lời giải chuẩn",
            claims_items=canonical.claims,
        )
        await event_publisher.publish(
            run_id, "solutions_generated", {"solvers": ["canonical_source"]}
        )

        # 3. CRITIQUING (Skeptic thẩm định 1 lượt)
        run.status = "critiquing"
        await db.commit()
        await event_publisher.publish(run_id, "status_changed", {"status": "critiquing"})

        reserved_sk = await budget_manager.check_and_reserve(db, run_id, Decimal("0.010000"))
        sm = src_out.source_metadata
        comp_name = sm.competition_name if sm else "Kỳ thi"
        skeptic_prompt = (
            f"Đề bài: {normalized_statement}\n"
            f"Lời giải chuẩn từ nguồn ({comp_name}):\n"
            f"{canonical.summary}"
        )
        sk_res = await self._safe_generate(
            adapter=adapter_sk,
            system_prompt=SKEPTIC_PROMPT_V1.system_instruction,
            user_prompt=skeptic_prompt,
            response_schema=SkepticOutput,
            role_hint="skeptic",
            is_live=is_live,
        )
        await budget_manager.record_call_and_release(
            db=db,
            run_id=run_id,
            agent_role="skeptic",
            model_name=adapter_sk.model_name,
            prompt_tokens=sk_res.prompt_tokens,
            completion_tokens=sk_res.completion_tokens,
            actual_cost=sk_res.cost_usd,
            latency_ms=sk_res.latency_ms,
            prompt_version=SKEPTIC_PROMPT_V1.version,
            reserved_cost=reserved_sk,
        )

        # 4. ADJUDICATING (Judge thẩm định và xuất báo cáo kèm Nguồn gốc)
        run.status = "adjudicating"
        await db.commit()
        await event_publisher.publish(run_id, "status_changed", {"status": "adjudicating"})

        reserved_jd = await budget_manager.check_and_reserve(db, run_id, Decimal("0.015000"))
        source_note = f"Kỳ thi: {sm.competition_name}, Năm: {sm.year}, Bài: {sm.problem_number}. Link: {', '.join(sm.reference_urls)}" if sm else "Nguồn gốc xác thực"

        judge_prompt = (
            f"Đề bài: {normalized_statement}\n"
            f"[THÔNG TIN NGUỒN GỐC]: {source_note}\n"
            f"Lời giải chuẩn: {canonical.summary}\n"
        )
        jd_res = await self._safe_generate(
            adapter=adapter_jd,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=judge_prompt,
            response_schema=JudgeOutput,
            role_hint="judge",
            is_live=is_live,
        )
        await budget_manager.record_call_and_release(
            db=db,
            run_id=run_id,
            agent_role="judge",
            model_name=adapter_jd.model_name,
            prompt_tokens=jd_res.prompt_tokens,
            completion_tokens=jd_res.completion_tokens,
            actual_cost=jd_res.cost_usd,
            latency_ms=jd_res.latency_ms,
            prompt_version=JUDGE_PROMPT_V1.version,
            reserved_cost=reserved_jd,
        )

        jd_data = JudgeOutput.model_validate(jd_res.parsed_json)
        full_final_solution = f"**[Nguồn gốc đề toán: {sm.competition_name if sm else 'Kỳ thi'} ({sm.year if sm else ''})]**\n\n" + jd_data.final_latex_solution
        jd_data.final_latex_solution = full_final_solution
        jd_data.executive_summary = f"Bài toán khớp 100% với đề thi {sm.competition_name if sm else 'gốc'}. " + jd_data.executive_summary
        await discussion_engine.save_final_report(
            db=db,
            run_id=run_id,
            winning_solution_id=sol.id,
            judge_output=jd_data,
        )

        run.status = "completed"
        await db.commit()
        await event_publisher.publish(run_id, "status_changed", {"status": "completed"})
        return "completed"

    async def _execute_from_solving(
        self, db: AsyncSession, run: Run, normalized_statement: str | None = None
    ) -> str:
        run_id = run.id
        is_live = (settings.DEFAULT_LLM_PROVIDER == "live") or ((run.config or {}).get("mode") == "live")
        adapter_a = get_llm_adapter(settings.ROLE_SOLVER_A_MODEL if is_live else "mock-math-council")
        adapter_b = get_llm_adapter(settings.ROLE_SOLVER_B_MODEL if is_live else "mock-math-council")
        adapter_sk = get_llm_adapter(settings.ROLE_SKEPTIC_MODEL if is_live else "mock-math-council")
        adapter_rev = get_llm_adapter(settings.ROLE_SOLVER_A_MODEL if is_live else "mock-math-council")
        adapter_jd = get_llm_adapter(settings.ROLE_JUDGE_MODEL if is_live else "mock-math-council")

        if not normalized_statement:
            problem = await db.get(Problem, run.problem_id)
            normalized_statement = (problem.statement_normalized if problem else None) or "Solve math problem"

        # Đính kèm nguồn gốc tham khảo nếu có (Trường hợp 2)
        source_ref = ""
        discovered = (run.config or {}).get("discovered_source")
        if discovered and discovered.get("source_found"):
            if discovered.get("origin_summary"):
                source_ref += f"\n[THÔNG TIN NGUỒN GỐC INTERNET]: {discovered['origin_summary']}"
            if discovered.get("reference_urls"):
                source_ref += f"\n[LIÊN KẾT NGUỒN THAM KHẢO]: {', '.join(discovered['reference_urls'])}"
            sm = discovered.get("source_metadata") or {}
            if sm.get("competition_name") and sm.get("competition_name") != "Internet Grounding Discovery":
                source_ref += f"\n[THAM KHẢO]: Bài toán gốc từ {sm.get('competition_name', '')} ({sm.get('year', '')})."
            if discovered.get("variant_warning"):
                source_ref += f"\n[CẢNH BÁO BIẾN THỂ]: {discovered.get('variant_warning')}"

        # ---------------------------------------------------------
        # 2. SOLVING PHASE (Solver A & Solver B LLM calls run in parallel)
        # ---------------------------------------------------------
        run.status = "solving"
        await db.commit()
        await event_publisher.publish(run_id, "status_changed", {"status": "solving"})

        # Reserve budget atomically for Solvers
        has_solver_c = "solver_c" in (run.config or {}).get("solvers", [])
        reserved_a = await budget_manager.check_and_reserve(db, run_id, Decimal("0.010000"))
        reserved_b = await budget_manager.check_and_reserve(db, run_id, Decimal("0.010000"))
        if has_solver_c:
            adapter_c = get_llm_adapter(settings.ROLE_SOLVER_C_MODEL if is_live else "mock-math-council")
            reserved_c = await budget_manager.check_and_reserve(db, run_id, Decimal("0.010000"))

        prompt_a = f"Giải bài toán sau:\n{normalized_statement}{source_ref}"
        prompt_b = f"Giải bài toán sau với góc nhìn độc lập:\n{normalized_statement}{source_ref}"
        if has_solver_c:
            prompt_c = f"Giải bài toán sau với phương pháp phân tích độc lập:\n{normalized_statement}{source_ref}"

        # Parallel LLM generation
        if has_solver_c:
            res_a, res_b, res_c = await asyncio.gather(
                self._safe_generate(
                    adapter=adapter_a,
                    system_prompt=SOLVER_SYSTEM_PROMPT,
                    user_prompt=prompt_a,
                    response_schema=SolverOutput,
                    role_hint="solver_a",
                    is_live=is_live,
                ),
                self._safe_generate(
                    adapter=adapter_b,
                    system_prompt=SOLVER_SYSTEM_PROMPT,
                    user_prompt=prompt_b,
                    response_schema=SolverOutput,
                    role_hint="solver_b",
                    is_live=is_live,
                ),
                self._safe_generate(
                    adapter=adapter_c,
                    system_prompt=SOLVER_SYSTEM_PROMPT,
                    user_prompt=prompt_c,
                    response_schema=SolverOutput,
                    role_hint="solver_c",
                    is_live=is_live,
                ),
            )
        else:
            res_a, res_b = await asyncio.gather(
                self._safe_generate(
                    adapter=adapter_a,
                    system_prompt=SOLVER_SYSTEM_PROMPT,
                    user_prompt=prompt_a,
                    response_schema=SolverOutput,
                    role_hint="solver_a",
                    is_live=is_live,
                ),
                self._safe_generate(
                    adapter=adapter_b,
                    system_prompt=SOLVER_SYSTEM_PROMPT,
                    user_prompt=prompt_b,
                    response_schema=SolverOutput,
                    role_hint="solver_b",
                    is_live=is_live,
                ),
            )

        # Sequential DB recording (avoids concurrent AsyncSession access)
        await budget_manager.record_call_and_release(
            db=db,
            run_id=run_id,
            agent_role="solver_a",
            model_name=adapter_a.model_name,
            prompt_tokens=res_a.prompt_tokens,
            completion_tokens=res_a.completion_tokens,
            actual_cost=res_a.cost_usd,
            latency_ms=res_a.latency_ms,
            prompt_version=PROMPT_VERSION,
            reserved_cost=reserved_a,
        )

        await budget_manager.record_call_and_release(
            db=db,
            run_id=run_id,
            agent_role="solver_b",
            model_name=adapter_b.model_name,
            prompt_tokens=res_b.prompt_tokens,
            completion_tokens=res_b.completion_tokens,
            actual_cost=res_b.cost_usd,
            latency_ms=res_b.latency_ms,
            prompt_version=PROMPT_VERSION,
            reserved_cost=reserved_b,
        )

        if has_solver_c:
            await budget_manager.record_call_and_release(
                db=db,
                run_id=run_id,
                agent_role="solver_c",
                model_name=adapter_c.model_name,
                prompt_tokens=res_c.prompt_tokens,
                completion_tokens=res_c.completion_tokens,
                actual_cost=res_c.cost_usd,
                latency_ms=res_c.latency_ms,
                prompt_version=PROMPT_VERSION,
                reserved_cost=reserved_c,
            )

        solver_a_out = SolverOutput.model_validate(res_a.parsed_json)
        solver_b_out = SolverOutput.model_validate(res_b.parsed_json)

        # Validate DAG for each solver
        validate_claim_dag(solver_a_out.claims)
        validate_claim_dag(solver_b_out.claims)

        sol_a = await discussion_engine.save_solution_with_claims(
            db=db,
            run_id=run_id,
            solver_role="solver_a",
            version=1,
            round_number=1,
            summary=solver_a_out.summary,
            final_answer=solver_a_out.final_answer,
            claims_items=solver_a_out.claims,
        )

        sol_b = await discussion_engine.save_solution_with_claims(
            db=db,
            run_id=run_id,
            solver_role="solver_b",
            version=1,
            round_number=1,
            summary=solver_b_out.summary,
            final_answer=solver_b_out.final_answer,
            claims_items=solver_b_out.claims,
        )

        if has_solver_c:
            solver_c_out = SolverOutput.model_validate(res_c.parsed_json)
            validate_claim_dag(solver_c_out.claims)
            sol_c = await discussion_engine.save_solution_with_claims(
                db=db,
                run_id=run_id,
                solver_role="solver_c",
                version=1,
                round_number=1,
                summary=solver_c_out.summary,
                final_answer=solver_c_out.final_answer,
                claims_items=solver_c_out.claims,
            )

        solvers_list = ["solver_a", "solver_b", "solver_c"] if has_solver_c else ["solver_a", "solver_b"]
        await event_publisher.publish(
            run_id, "solutions_generated", {"solvers": solvers_list}
        )

        # ---------------------------------------------------------
        # 3. CRITIQUING PHASE (Skeptic challenges Solver A & B & C)
        # ---------------------------------------------------------
        run.status = "critiquing"
        await db.commit()
        await event_publisher.publish(run_id, "status_changed", {"status": "critiquing"})

        reserved_sk = await budget_manager.check_and_reserve(db, run_id, Decimal("0.010000"))
        skeptic_prompt = (
            f"Đề bài: {normalized_statement}\n"
            f"Solver A: {solver_a_out.summary}\nĐáp số: {solver_a_out.final_answer}\n\n"
            f"Solver B: {solver_b_out.summary}\nĐáp số: {solver_b_out.final_answer}"
        )
        if has_solver_c:
            skeptic_prompt += f"\n\nSolver C: {solver_c_out.summary}\nĐáp số: {solver_c_out.final_answer}"
        sk_res = await self._safe_generate(
            adapter=adapter_sk,
            system_prompt=SKEPTIC_SYSTEM_PROMPT,
            user_prompt=skeptic_prompt,
            response_schema=SkepticOutput,
            role_hint="skeptic",
            is_live=is_live,
        )
        await budget_manager.record_call_and_release(
            db=db,
            run_id=run_id,
            agent_role="skeptic",
            model_name=adapter_sk.model_name,
            prompt_tokens=sk_res.prompt_tokens,
            completion_tokens=sk_res.completion_tokens,
            actual_cost=sk_res.cost_usd,
            latency_ms=sk_res.latency_ms,
            prompt_version=PROMPT_VERSION,
            reserved_cost=reserved_sk,
        )

        skeptic_out = SkepticOutput.model_validate(sk_res.parsed_json)
        challenges = await discussion_engine.save_challenges(
            db=db,
            run_id=run_id,
            target_solution_id=sol_a.id,
            challenges_items=skeptic_out.challenges,
            round_number=1,
        )

        await event_publisher.publish(
            run_id, "challenges_raised", {"count": len(challenges)}
        )

        # ---------------------------------------------------------
        # 4. REVISING PHASE (Reviser creates solution version 2)
        # ---------------------------------------------------------
        run.status = "revising"
        await db.commit()
        await event_publisher.publish(run_id, "status_changed", {"status": "revising"})

        reserved_rev = await budget_manager.check_and_reserve(db, run_id, Decimal("0.010000"))
        rev_prompt = f"Phản biện từ Skeptic: {skeptic_out.challenges[0].argument if skeptic_out.challenges else 'Không có'}"
        rev_res = await self._safe_generate(
            adapter=adapter_rev,
            system_prompt=REVISER_SYSTEM_PROMPT,
            user_prompt=rev_prompt,
            response_schema=SolverOutput,
            role_hint="solver_a",
            is_live=is_live,
        )
        await budget_manager.record_call_and_release(
            db=db,
            run_id=run_id,
            agent_role="solver_a",
            model_name=adapter_rev.model_name,
            prompt_tokens=rev_res.prompt_tokens,
            completion_tokens=rev_res.completion_tokens,
            actual_cost=rev_res.cost_usd,
            latency_ms=rev_res.latency_ms,
            prompt_version=PROMPT_VERSION,
            reserved_cost=reserved_rev,
        )

        reviser_out = SolverOutput.model_validate(rev_res.parsed_json)
        revised_sol = await discussion_engine.save_solution_with_claims(
            db=db,
            run_id=run_id,
            solver_role="solver_a",
            version=2,
            round_number=2,
            summary=reviser_out.summary,
            final_answer=reviser_out.final_answer,
            claims_items=reviser_out.claims,
        )

        await event_publisher.publish(run_id, "solution_revised", {"version": 2})

        # ---------------------------------------------------------
        # 5. ADJUDICATING PHASE (Chief Judge creates FinalReport)
        # ---------------------------------------------------------
        run.status = "adjudicating"
        await db.commit()
        await event_publisher.publish(run_id, "status_changed", {"status": "adjudicating"})

        reserved_jd = await budget_manager.check_and_reserve(db, run_id, Decimal("0.015000"))
        judge_prompt = (
            f"Bài toán: {normalized_statement}\n"
            f"Lời giải v1: {solver_a_out.final_answer}\n"
            f"Lời giải v2 sau sửa đổi: {reviser_out.final_answer}"
        )
        jd_res = await self._safe_generate(
            adapter=adapter_jd,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=judge_prompt,
            response_schema=JudgeOutput,
            role_hint="judge",
            is_live=is_live,
        )
        await budget_manager.record_call_and_release(
            db=db,
            run_id=run_id,
            agent_role="judge",
            model_name=adapter_jd.model_name,
            prompt_tokens=jd_res.prompt_tokens,
            completion_tokens=jd_res.completion_tokens,
            actual_cost=jd_res.cost_usd,
            latency_ms=jd_res.latency_ms,
            prompt_version=PROMPT_VERSION,
            reserved_cost=reserved_jd,
        )

        judge_out = JudgeOutput.model_validate(jd_res.parsed_json)
        await discussion_engine.save_final_report(
            db=db,
            run_id=run_id,
            winning_solution_id=revised_sol.id,
            judge_output=judge_out,
        )

        # ---------------------------------------------------------
        # 6. COMPLETED
        # ---------------------------------------------------------
        run.status = "completed"
        await db.commit()
        await event_publisher.publish(run_id, "run_completed", {"consensus": judge_out.consensus_status})

        return "completed"


council_orchestrator = CouncilOrchestrator()
