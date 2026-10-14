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
    claim_id: str = Field(..., pattern=r"^C[1-9][0-9]*$")
    statement: str
    reasoning: str
    depends_on: list[str] = Field(default_factory=list)
    status: ClaimStatus = Field(default="unverified")


class ProofStepSchema(BaseModel):
    step_id: str = Field(..., pattern=r"^S[1-9][0-9]*$")
    claim_refs: list[str] = Field(default_factory=list)
    content: str


class SolverOutputSchema(BaseModel):
    task_type: Literal["solve", "revise"] = "solve"
    status: Literal["completed", "partial", "failed"] = "completed"
    summary: str
    claims: list[ClaimItemSchema] = Field(..., min_length=1)
    proof_steps: list[ProofStepSchema] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "medium"


class SourceDiscoveryOutputSchema(BaseModel):
    match_type: Literal["exact_match", "modified_variant", "no_match"] = Field(
        ..., description="Phân loại mức độ khớp với bài toán gốc trong ngân hàng đề"
    )
    source_found: bool = Field(default=False, description="Có tìm thấy nguồn gốc đề bài không")
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
    label: str = Field(..., description="Định danh mệnh đề: C1, C2,...")
    content: str = Field(..., description="Nội dung khẳng định hoặc bước biến đổi toán học")
    claim_type: Literal["fact", "inference", "calculation", "conjecture", "definition"] = "inference"
    depends_on: list[str] = Field(default_factory=list, description="Danh sách nhãn mệnh đề tiên quyết")


class SolverOutput(BaseModel):
    summary: str = Field(..., description="Tóm tắt ý tưởng giải")
    claims: list[ClaimItem] = Field(..., min_length=1, description="Các bước suy luận dạng mệnh đề có cấu trúc")
    final_answer: str = Field(..., description="Đáp số hoặc kết luận cuối cùng")


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
