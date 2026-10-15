from typing import Any, Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

# ==============================================================================
# SCHEMA SET A (Math Council Master & Multi-LLM Contracts)
# ==============================================================================

ClaimStatus = Literal["unverified", "supported", "disputed", "rejected"]

ChallengeErrorType = Literal[
    "valid",
    "invalid_inference",
    "missing_case",
    "unsupported_claim",
    "incorrect_calculation",
    "ambiguous_statement",
    "needs_more_evidence",
]

ChallengeSeverity = Literal["minor", "major", "critical"]
ChallengeStatus = Literal["open", "accepted", "rejected", "unresolved"]
ConfidenceLevel = Literal["low", "medium", "high"]


class NormalizationOutputSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    statement_normalized: str = Field(
        ...,
        validation_alias=AliasChoices("statement_normalized", "normalized_statement", "normalized_problem_statement"),
        description="Đề toán đã chuẩn hóa LaTeX.",
    )
    needs_clarification: bool = Field(
        default=False,
        validation_alias=AliasChoices("needs_clarification", "has_ambiguity", "is_ambiguous"),
    )
    clarification_reason: str | None = Field(
        default=None,
        validation_alias=AliasChoices("clarification_reason", "ambiguity_warning", "warning"),
    )
    detected_subject: str | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def unify_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ["normalized_statement", "normalized_problem_statement", "normalized_problem", "statement"]:
                if key in data and "statement_normalized" not in data:
                    data["statement_normalized"] = data[key]
            if "has_ambiguity" in data and "needs_clarification" not in data:
                data["needs_clarification"] = data["has_ambiguity"]
            if "ambiguity_warning" in data and "clarification_reason" not in data:
                data["clarification_reason"] = data["ambiguity_warning"]
        return data


class SourceMetadataSchema(BaseModel):
    competition_name: str = Field(..., description="Tên kỳ thi toán học (ví dụ: IMO, VMO, Putnam, AoPS)")
    year: int | None = Field(default=None, description="Năm thi")
    problem_number: str | None = Field(default=None, description="Số thứ tự bài thi (ví dụ: Problem 1, Bài 4)")
    reference_urls: list[str] = Field(default_factory=list, description="Danh sách liên kết nguồn (ví dụ: AoPS)")


class ClaimItemSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    claim_id: str = Field(default="C1", validation_alias=AliasChoices("claim_id", "label", "id"), pattern=r"^C[1-9][0-9]*$")
    statement: str = Field(default="Bước suy luận toán học", validation_alias=AliasChoices("statement", "content", "claim", "text"))
    reasoning: str = Field(default="Biến đổi trực tiếp từ giả thiết.", validation_alias=AliasChoices("reasoning", "explanation", "details"))
    depends_on: list[str] = Field(default_factory=list)
    status: ClaimStatus = Field(default="unverified")

    @model_validator(mode="before")
    @classmethod
    def unify_claim_item_schema(cls, data: Any) -> Any:
        import re
        if isinstance(data, str):
            return {
                "claim_id": "C1",
                "statement": data,
                "reasoning": "Biến đổi đại số hoặc suy luận trực tiếp.",
                "depends_on": [],
                "status": "unverified",
            }
        if isinstance(data, dict):
            cid = data.get("claim_id") or data.get("label") or data.get("id") or "C1"
            cid_str = str(cid)
            if not cid_str.startswith("C") or not cid_str[1:].isdigit():
                nums = re.findall(r"\d+", cid_str)
                cid_str = f"C{nums[0]}" if nums else "C1"
            data["claim_id"] = cid_str
            if "statement" not in data:
                data["statement"] = data.get("content") or data.get("claim") or data.get("text") or "Bước suy luận toán học"
            if "reasoning" not in data:
                data["reasoning"] = data.get("explanation") or data.get("details") or "Biến đổi trực tiếp từ giả thiết."
            if "depends_on" not in data or not isinstance(data.get("depends_on"), list):
                data["depends_on"] = []
            if "status" not in data:
                data["status"] = "unverified"
        return data


class ProofStepSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    step_id: str = Field(default="S1", validation_alias=AliasChoices("step_id", "id"), pattern=r"^S[1-9][0-9]*$")
    claim_refs: list[str] = Field(default_factory=list)
    content: str = Field(default="Hoàn tất bước lập luận.")


class SolverOutputSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    task_type: Literal["solve", "revise"] = "solve"
    status: Literal["completed", "partial", "failed"] = "completed"
    summary: str = Field(default="Tóm tắt lời giải toán học", validation_alias=AliasChoices("summary", "approach", "overview"))
    claims: list[ClaimItemSchema] = Field(default_factory=list)
    proof_steps: list[ProofStepSchema] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "medium"
    final_answer: str | None = Field(default="Xem chi tiết lời giải", validation_alias=AliasChoices("final_answer", "answer", "result", "conclusion"))
    solution: str | None = Field(default=None, validation_alias=AliasChoices("solution", "full_solution", "latex_solution", "proof"))
    reasoning_content: str | None = Field(default=None, description="Chuỗi suy luận reasoning tokens / thinking content")

    @model_validator(mode="before")
    @classmethod
    def unify_solver_schema(cls, data: Any) -> Any:
        if isinstance(data, str):
            sol = data.strip()
            return {
                "task_type": "solve",
                "status": "completed",
                "summary": sol[:300].strip() or "Lời giải toán học",
                "claims": [{"claim_id": "C1", "statement": sol, "reasoning": "Suy luận toán học", "depends_on": []}],
                "proof_steps": [{"step_id": "S1", "claim_refs": ["C1"], "content": sol}],
                "final_answer": "Xem chi tiết lời giải",
                "solution": sol,
            }
        if isinstance(data, dict):
            raw_solution = (
                data.get("solution")
                or data.get("full_solution")
                or data.get("latex_solution")
                or data.get("final_solution")
                or data.get("proof")
            )
            if raw_solution and not data.get("solution"):
                data["solution"] = str(raw_solution)

            if not data.get("summary"):
                if raw_solution and isinstance(raw_solution, str):
                    lines = [ln.strip() for ln in raw_solution.split("\n") if ln.strip()]
                    data["summary"] = (" ".join(lines[:3]) if lines else raw_solution)[:300].strip()
                elif data.get("claims") and isinstance(data["claims"], list) and len(data["claims"]) > 0:
                    c0 = data["claims"][0]
                    c_text = c0.get("statement") or c0.get("content") if isinstance(c0, dict) else str(c0)
                    data["summary"] = str(c_text)[:300]
                else:
                    data["summary"] = "Phân tích và giải quyết bài toán qua các bước logic."

            if not data.get("final_answer"):
                cand_ans = (
                    data.get("answer")
                    or data.get("result")
                    or data.get("conclusion")
                    or data.get("final_result")
                )
                if cand_ans:
                    data["final_answer"] = str(cand_ans).strip()
                elif raw_solution and isinstance(raw_solution, str):
                    lines = [ln.strip() for ln in raw_solution.split("\n") if ln.strip()]
                    data["final_answer"] = (lines[-1] if lines else raw_solution)[:300].strip()
                elif data.get("claims") and isinstance(data["claims"], list) and len(data["claims"]) > 0:
                    c_last = data["claims"][-1]
                    c_text = c_last.get("statement") or c_last.get("content") if isinstance(c_last, dict) else str(c_last)
                    data["final_answer"] = str(c_text)[:300]
                else:
                    data["final_answer"] = "Xem kết luận trong lời giải chi tiết."

            raw_claims = data.get("claims")
            if not raw_claims or not isinstance(raw_claims, list) or len(raw_claims) == 0:
                claim_text = (
                    (raw_solution if isinstance(raw_solution, str) else "")
                    or str(data.get("summary") or "Thực hiện biến đổi và suy luận toán học.")
                )
                data["claims"] = [
                    {
                        "claim_id": "C1",
                        "statement": claim_text,
                        "reasoning": "Biến đổi đại số hoặc suy luận trực tiếp.",
                        "depends_on": [],
                        "status": "unverified",
                    }
                ]
            else:
                formatted = []
                for i, c in enumerate(raw_claims, 1):
                    if isinstance(c, str):
                        formatted.append({
                            "claim_id": f"C{i}",
                            "statement": c,
                            "reasoning": "Bước suy luận.",
                            "depends_on": [f"C{i-1}"] if i > 1 else [],
                            "status": "unverified",
                        })
                    elif isinstance(c, dict):
                        cd = dict(c)
                        if not cd.get("claim_id"):
                            cd["claim_id"] = cd.get("label") or cd.get("id") or f"C{i}"
                        if not cd.get("statement"):
                            cd["statement"] = cd.get("content") or cd.get("claim") or cd.get("text") or f"Mệnh đề {i}"
                        if not cd.get("reasoning"):
                            cd["reasoning"] = cd.get("explanation") or "Suy luận trực tiếp."
                        if "depends_on" not in cd or not isinstance(cd["depends_on"], list):
                            cd["depends_on"] = []
                        formatted.append(cd)
                    else:
                        formatted.append({
                            "claim_id": f"C{i}",
                            "statement": str(c),
                            "reasoning": "Bước suy luận.",
                            "depends_on": [],
                            "status": "unverified",
                        })
                data["claims"] = formatted

            if not data.get("proof_steps") or not isinstance(data.get("proof_steps"), list) or len(data.get("proof_steps")) == 0:
                data["proof_steps"] = [
                    {
                        "step_id": "S1",
                        "claim_refs": [c["claim_id"] for c in data["claims"]],
                        "content": data.get("summary") or (raw_solution if isinstance(raw_solution, str) else "Hoàn tất chứng minh."),
                    }
                ]

            if not data.get("solution"):
                if raw_solution:
                    data["solution"] = raw_solution
                else:
                    claims_lines = "\n".join([f"- [{c['claim_id']}]: {c['statement']}" for c in data["claims"]])
                    data["solution"] = (
                        f"### Tóm tắt ý tưởng\n{data.get('summary', '')}\n\n"
                        f"### Các bước suy luận (Claims)\n{claims_lines}\n\n"
                        f"### Đáp số / Kết luận\n{data.get('final_answer', '')}"
                    )
        return data


class SourceDiscoveryOutputSchema(BaseModel):
    match_type: Literal["exact_match", "modified_variant", "no_match"] = Field(
        default="modified_variant", description="Phân loại mức độ khớp với bài toán gốc trong ngân hàng đề"
    )
    source_found: bool = Field(default=False, description="Có tìm thấy nguồn gốc đề bài không")
    origin_summary: str | None = Field(
        default=None, description="Nội dung tóm tắt nguồn gốc từ tìm kiếm Internet"
    )
    reference_urls: list[str] = Field(
        default_factory=list, description="Danh sách URL tham khảo từ grounding_metadata"
    )
    source_metadata: SourceMetadataSchema | None = Field(
        default=None, description="Thông tin chi tiết về kỳ thi và bài toán gốc"
    )
    variant_warning: str | None = Field(
        default=None, description="Cảnh báo nếu đề đã bị thay đổi hằng số, điều kiện so với đề gốc"
    )
    canonical_solution: SolverOutputSchema | None = Field(
        default=None, description="Lời giải chuẩn từ nguồn tham khảo, phân rã thành claims và proof_steps"
    )


class ChallengeItemSchema(BaseModel):
    target_claim_id: str
    error_type: ChallengeErrorType
    severity: ChallengeSeverity
    explanation: str
    counterexample: str | None = Field(default=None)
    required_fix: str


class SkepticOutputSchema(BaseModel):
    task_type: Literal["critique"] = "critique"
    overall_assessment: str
    challenges: list[ChallengeItemSchema] = Field(default_factory=list)
    confidence: ConfidenceLevel = "high"


class ChallengeResponseItemSchema(BaseModel):
    target_claim_id: str
    action: Literal["revised", "defended", "acknowledged_unresolved"]
    response_explanation: str


class SolverRevisionOutputSchema(BaseModel):
    task_type: Literal["revise"] = "revise"
    revised_solution: SolverOutputSchema
    challenge_responses: list[ChallengeResponseItemSchema] = Field(default_factory=list)


class ChallengeAdjudicationItemSchema(BaseModel):
    target_claim_id: str
    new_status: Literal["accepted", "rejected", "unresolved"]
    reason: str


class JudgeOutputSchema(BaseModel):
    task_type: Literal["adjudicate"] = "adjudicate"
    verdict_status: Literal["supported", "disputed", "unresolved", "rejected"]
    selected_solver_role: Literal["solver_a", "solver_b", "solver_c", "none"] = "none"
    summary: str
    final_proof_markdown: str
    challenge_adjudications: list[ChallengeAdjudicationItemSchema] = Field(default_factory=list)
    accepted_claims: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)


# ==============================================================================
# SCHEMA SET B (Legacy & State Machine Compatibility Contracts)
# ==============================================================================

class NormalizerOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    normalized_statement: str = Field(
        ...,
        validation_alias=AliasChoices(
            "normalized_statement",
            "normalized_problem_statement",
            "statement_normalized",
            "normalized_problem",
        ),
        description="Đề toán sau khi chuẩn hóa ký hiệu LaTeX",
    )
    assumptions: list[str] = Field(default_factory=list, description="Các giả thiết ngầm định hoặc điều kiện xác định")
    extracted_variables: dict[str, str] = Field(default_factory=dict, description="Các biến số và miền giá trị")
    has_ambiguity: bool = Field(
        default=False,
        validation_alias=AliasChoices("has_ambiguity", "needs_clarification", "is_ambiguous"),
        description="Đề toán có mơ hồ hoặc thiếu dữ kiện nghiêm trọng không",
    )
    ambiguity_warning: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ambiguity_warning", "clarification_reason", "warning"),
        description="Cảnh báo chi tiết nếu phát hiện đề mơ hồ",
    )
    detected_subject: str | None = Field(
        default=None,
        description="Phân môn toán học: Số học, Đại số, Tổ hợp / Toán rời rạc, Hình học, Bất đẳng thức",
    )

    @model_validator(mode="before")
    @classmethod
    def unify_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ["normalized_problem_statement", "statement_normalized", "normalized_problem", "statement"]:
                if key in data and "normalized_statement" not in data:
                    data["normalized_statement"] = data[key]
            if "needs_clarification" in data and "has_ambiguity" not in data:
                data["has_ambiguity"] = data["needs_clarification"]
            if "clarification_reason" in data and "ambiguity_warning" not in data:
                data["ambiguity_warning"] = data["clarification_reason"]
        return data


class ClaimItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    label: str = Field(default="C1", validation_alias=AliasChoices("label", "claim_id", "id", "name"), description="Định danh mệnh đề: C1, C2,...")
    content: str = Field(default="Nội dung bước suy luận", validation_alias=AliasChoices("content", "statement", "reasoning", "claim", "text", "description"), description="Nội dung khẳng định hoặc bước biến đổi toán học")
    claim_type: Literal["fact", "inference", "calculation", "conjecture", "definition"] = Field(default="inference", validation_alias=AliasChoices("claim_type", "type"))
    depends_on: list[str] = Field(default_factory=list, description="Danh sách nhãn mệnh đề tiên quyết")

    @model_validator(mode="before")
    @classmethod
    def unify_claim_item(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {
                "label": "C1",
                "content": data,
                "claim_type": "inference",
                "depends_on": [],
            }
        if isinstance(data, dict):
            if "label" not in data:
                data["label"] = data.get("claim_id") or data.get("id") or "C1"
            if "content" not in data:
                data["content"] = data.get("statement") or data.get("reasoning") or data.get("text") or "Bước suy luận toán học"
            if "claim_type" not in data:
                data["claim_type"] = "inference"
            if "depends_on" not in data or not isinstance(data.get("depends_on"), list):
                data["depends_on"] = []
            else:
                data["depends_on"] = [str(x) for x in data["depends_on"]]
        return data


class SolverOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    summary: str = Field(
        default="Tóm tắt ý tưởng và phương pháp giải toán",
        validation_alias=AliasChoices("summary", "approach", "overview", "solution_summary"),
        description="Tóm tắt ý tưởng giải",
    )
    claims: list[ClaimItem] = Field(
        default_factory=list,
        description="Các bước suy luận dạng mệnh đề có cấu trúc",
    )
    final_answer: str = Field(
        default="Xem chi tiết lời giải",
        validation_alias=AliasChoices("final_answer", "answer", "result", "conclusion", "final_result"),
        description="Đáp số hoặc kết luận cuối cùng",
    )
    solution: str | None = Field(
        default=None,
        validation_alias=AliasChoices("solution", "full_solution", "latex_solution", "proof", "final_solution"),
        description="Toàn bộ lời giải chi tiết bằng LaTeX",
    )
    reasoning_content: str | None = Field(
        default=None,
        description="Chuỗi suy luận reasoning tokens / thinking content",
    )

    @model_validator(mode="before")
    @classmethod
    def unify_solver_output(cls, data: Any) -> Any:
        if isinstance(data, str):
            sol = data.strip()
            return {
                "summary": sol[:300].strip() or "Lời giải toán học",
                "claims": [{"label": "C1", "content": sol, "claim_type": "inference", "depends_on": []}],
                "final_answer": "Xem chi tiết lời giải",
                "solution": sol,
            }

        if isinstance(data, dict):
            raw_solution = (
                data.get("solution")
                or data.get("full_solution")
                or data.get("latex_solution")
                or data.get("final_solution")
                or data.get("proof")
            )
            if raw_solution and not data.get("solution"):
                data["solution"] = str(raw_solution)

            if not data.get("summary"):
                if raw_solution and isinstance(raw_solution, str):
                    lines = [ln.strip() for ln in raw_solution.split("\n") if ln.strip()]
                    data["summary"] = (" ".join(lines[:3]) if lines else raw_solution)[:300].strip()
                elif data.get("claims") and isinstance(data["claims"], list) and len(data["claims"]) > 0:
                    c0 = data["claims"][0]
                    c_text = c0.get("content") or c0.get("statement") if isinstance(c0, dict) else str(c0)
                    data["summary"] = str(c_text)[:300]
                else:
                    data["summary"] = "Phân tích và giải quyết bài toán qua các bước logic."

            if not data.get("final_answer"):
                cand_ans = (
                    data.get("answer")
                    or data.get("result")
                    or data.get("conclusion")
                    or data.get("final_result")
                )
                if cand_ans:
                    data["final_answer"] = str(cand_ans).strip()
                elif raw_solution and isinstance(raw_solution, str):
                    lines = [ln.strip() for ln in raw_solution.split("\n") if ln.strip()]
                    data["final_answer"] = (lines[-1] if lines else raw_solution)[:300].strip()
                elif data.get("claims") and isinstance(data["claims"], list) and len(data["claims"]) > 0:
                    c_last = data["claims"][-1]
                    c_text = c_last.get("content") or c_last.get("statement") if isinstance(c_last, dict) else str(c_last)
                    data["final_answer"] = str(c_text)[:300]
                else:
                    data["final_answer"] = "Xem kết luận trong lời giải chi tiết."

            raw_claims = data.get("claims")
            if not raw_claims or not isinstance(raw_claims, list) or len(raw_claims) == 0:
                claim_text = (
                    (raw_solution if isinstance(raw_solution, str) else "")
                    or str(data.get("summary") or "Thực hiện biến đổi và suy luận toán học.")
                )
                data["claims"] = [
                    {
                        "label": "C1",
                        "content": claim_text,
                        "claim_type": "inference",
                        "depends_on": [],
                    }
                ]
            else:
                formatted_claims = []
                for i, c in enumerate(raw_claims, 1):
                    if isinstance(c, str):
                        formatted_claims.append({
                            "label": f"C{i}",
                            "content": c,
                            "claim_type": "inference",
                            "depends_on": [f"C{i-1}"] if i > 1 else [],
                        })
                    elif isinstance(c, dict):
                        c_dict = dict(c)
                        if not c_dict.get("label"):
                            c_dict["label"] = c_dict.get("claim_id") or c_dict.get("id") or f"C{i}"
                        if not c_dict.get("content"):
                            c_dict["content"] = c_dict.get("statement") or c_dict.get("reasoning") or c_dict.get("text") or f"Bước suy luận {i}"
                        if not c_dict.get("claim_type"):
                            c_dict["claim_type"] = "inference"
                        if "depends_on" not in c_dict or not isinstance(c_dict["depends_on"], list):
                            c_dict["depends_on"] = []
                        formatted_claims.append(c_dict)
                    else:
                        formatted_claims.append({
                            "label": f"C{i}",
                            "content": str(c),
                            "claim_type": "inference",
                            "depends_on": [],
                        })
                data["claims"] = formatted_claims

            if not data.get("solution"):
                if raw_solution:
                    data["solution"] = raw_solution
                else:
                    claims_lines = "\n".join([f"- [{c['label']}]: {c['content']}" for c in data["claims"]])
                    data["solution"] = (
                        f"### Tóm tắt ý tưởng\n{data.get('summary', '')}\n\n"
                        f"### Các bước suy luận (Claims)\n{claims_lines}\n\n"
                        f"### Đáp số / Kết luận\n{data.get('final_answer', '')}"
                    )

        return data


class ChallengeItem(BaseModel):
    target_claim_label: str | None = Field(default=None, description="Nhãn mệnh đề bị phản biện (ví dụ C2) hoặc None nếu phản biện toàn bài")
    error_type: Literal[
        "valid",
        "invalid_inference",
        "missing_case",
        "unsupported_claim",
        "incorrect_calculation",
        "ambiguous_statement",
        "needs_more_evidence",
    ] = Field(..., description="Phân loại lỗi theo quy tắc Bước 3")
    argument: str = Field(..., description="Lập luận phản biện chi tiết, chỉ rõ điểm sai hoặc phản ví dụ")


class SkepticOutput(BaseModel):
    challenges: list[ChallengeItem] = Field(default_factory=list, description="Danh sách các điểm phản biện đối với lời giải")


class JudgeOutput(BaseModel):
    consensus_status: Literal[
        "consensus_reached",
        "majority_agreed",
        "split_decision",
        "needs_human_review",
    ] = Field(..., description="Trạng thái đồng thuận của hội đồng")
    winning_solver: str | None = Field(default=None, description="Solver có lời giải chính xác nhất")
    final_latex_solution: str = Field(..., description="Lời giải tổng hợp hoàn chỉnh bằng LaTeX")
    executive_summary: str = Field(..., description="Báo cáo tóm tắt quá trình thảo luận và phân xử")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Độ tin cậy của lời giải từ 0.0 đến 1.0")
    dissenting_opinions: list[str] = Field(default_factory=list, description="Các ý kiến bảo lưu hoặc điểm chưa thống nhất")
