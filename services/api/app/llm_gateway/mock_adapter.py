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


def _detect_context(user_prompt: str) -> str:
    p = user_prompt.lower()
    if any(k in p for k in ["bàn cờ", "quân tượng", "quân hậu", "quân mã", "tổ hợp", "rời rạc", "lưới ô vuông", "đồ thị", "dirichlet", "pigeonhole", "đường chéo", "bishop", "chessboard"]):
        return "combinatorics_chessboard"
    elif any(k in p for k in ["chọn số", "alice", "bob", "hợp số", "tập s", "s = \\{", "trò chơi"]):
        return "game_theory"
    elif any(k in p for k in ["tam giác", "hình học", "vuông tại", "đường tròn", "góc"]):
        return "geometry"
    elif any(k in p for k in ["bất đẳng thức", "cauchy", "schwarz", "am-gm", "lớn hơn hoặc bằng"]):
        return "inequality"
    elif any(k in p for k in ["tích phân", "đạo hàm", "giải tích", "\\int"]):
        return "calculus"
    elif any(k in p for k in ["21n + 4", "14n + 3", "ước chung", "tối giản", "imo 1959"]):
        return "olympiad_euclid"
    return "quadratic"


class DeterministicMockAdapter(BaseLLMAdapter):
    """Deterministic Mock Adapter for testing without external API calls or costs.
    Dynamically tailors mock proofs to the problem's mathematical context.
    """

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
        ctx = _detect_context(user_prompt)

        parsed: dict[str, Any] = {}

        if response_schema is NormalizerOutput or (response_schema is None and "Chuyên gia Chuẩn hóa" in system_prompt):
            clean_stmt = user_prompt.strip()
            if "<untrusted_user_input>" in clean_stmt and "</untrusted_user_input>" in clean_stmt:
                clean_stmt = clean_stmt.split("<untrusted_user_input>")[1].split("</untrusted_user_input>")[0].strip()
            elif "<problem_statement>" in clean_stmt and "</problem_statement>" in clean_stmt:
                clean_stmt = clean_stmt.split("<problem_statement>")[1].split("</problem_statement>")[0].strip()
            if not clean_stmt:
                clean_stmt = "Cho phương trình $ax^2 + bx + c = 0$ ($a \\neq 0$)."

            if ctx == "combinatorics_chessboard":
                assump = ["Bàn cờ $N \\times N$", "Hai quân tượng không ăn nhau nếu không cùng đường chéo", "Tìm số quân tượng tối đa"]
                vars_dict = {"N": "kích thước bàn cờ", "2N-2": "số lượng quân tượng tối đa"}
            elif ctx == "game_theory":
                assump = ["$S = \\{1, 2, \\dots, n\\}$", "Alice và Bob chơi luân phiên", "Các số không lặp lại"]
                vars_dict = {"n": "số lượng phần tử trong tập hợp S", "S": "tập hợp các số nguyên từ 1 đến n"}
            elif ctx == "geometry":
                assump = ["Tam giác $ABC$ xét trong mặt phẳng Euclid", "Các đỉnh không thẳng hàng"]
                vars_dict = {"A, B, C": "các đỉnh của tam giác", "a, b, c": "độ dài các cạnh đối diện"}
            elif ctx == "inequality":
                assump = ["$a, b, c > 0$", "$a + b + c = 3$"]
                vars_dict = {"a, b, c": "các biến số thực dương thỏa mãn điều kiện"}
            else:
                assump = ["$a, b, c \\in \\mathbb{R}$", "$a \\neq 0$"]
                vars_dict = {"a": "hệ số bậc 2", "b": "hệ số bậc 1", "c": "hệ số tự do"}

            obj = NormalizerOutput(
                normalized_statement=clean_stmt,
                assumptions=assump,
                extracted_variables=vars_dict,
                has_ambiguity=False,
                ambiguity_warning=None,
            )
            parsed = obj.model_dump()

        elif response_schema is SkepticOutput or (response_schema is None and "Nhà Phản Biện" in system_prompt):
            if ctx == "combinatorics_chessboard":
                arg = "Cần phân hoạch đường chéo thành 2 lớp màu ô cờ độc lập và kiểm tra trường hợp biên N = 1."
            elif ctx == "game_theory":
                arg = "Cần chứng minh chặt chẽ tính chẵn lẻ của tổng với trường hợp nhỏ $n \\le 3$."
            elif ctx == "geometry":
                arg = "Cần kiểm tra kỹ tính suy biến của các góc khi điểm trùng nhau."
            elif ctx == "inequality":
                arg = "Cần chỉ rõ điều kiện dấu đẳng thức xảy ra khi các biến bằng 1."
            else:
                arg = "Cần xét rõ điều kiện $\\Delta \\ge 0$ trước khi khai căn số thực ở bước C3."

            obj = SkepticOutput(
                challenges=[
                    ChallengeItem(
                        target_claim_label="C2",
                        error_type="missing_case",
                        argument=arg,
                    )
                ]
            )
            parsed = obj.model_dump()

        elif response_schema is JudgeOutput or (response_schema is None and "Thẩm Định Viên" in system_prompt):
            if ctx == "combinatorics_chessboard":
                latex_sol = (
                    "**Lời giải bài toán quân tượng trên bàn cờ:**\n\n"
                    "Số lượng quân tượng tối đa có thể đặt lên bàn cờ $N \\times N$ sao cho không quân nào ăn nhau là $2N - 2$ với $N \\ge 2$ (và bằng $1$ với $N = 1$).\n\n"
                    "Chứng minh dựa trên phân hoạch $2N-1$ đường chéo song song và nguyên lý Dirichlet."
                )
                summary = "Hội đồng AI thống nhất phán quyết: Đáp số là $2N - 2$ (với $N \\ge 2$) bằng phương pháp phân hoạch đường chéo và Dirichlet."
            elif ctx == "game_theory":
                latex_sol = (
                    "**Kết luận chiến lược thắng của trò chơi:**\n\n"
                    "- Tổng tất cả các phần tử trong $S$ là $T_n = \\frac{n(n+1)}{2}$.\n"
                    "- Với $n \\ge 4$: **Alice có chiến lược thắng** bằng cách chọn số lẻ đầu tiên và duy trì tổng của mình là hợp số.\n"
                    "- Với $n \\in \\{1, 2, 3\\}$: **Bob có chiến lược thắng** do các tổng có thể tạo ra đều là số nguyên tố."
                )
                summary = "Hội đồng AI thống nhất phán quyết: Alice thắng khi $n \\ge 4$; Bob thắng khi $n \\le 3$."
            elif ctx == "geometry":
                latex_sol = (
                    "**Lời giải hình học:**\n\n"
                    "Áp dụng hệ thức lượng và định lý hình học trong tam giác, ta có các góc và tỉ số cạnh tương ứng hoàn toàn thỏa mãn yêu cầu đề toán."
                )
                summary = "Hội đồng AI xác nhận lời giải hình học chính xác và logic."
            elif ctx == "inequality":
                latex_sol = (
                    "**Chứng minh bất đẳng thức:**\n\n"
                    "Áp dụng kỹ thuật Cauchy-Schwarz dạng Engel:\n"
                    "$$\\sum_{cyc} \\frac{a}{1 + b^2} = \\sum_{cyc} \\left(a - \\frac{ab^2}{1 + b^2}\\right) \\ge (a+b+c) - \\sum_{cyc} \\frac{ab}{2} = 3 - \\frac{3}{2} = \\frac{3}{2}$$\n\n"
                    "Đẳng thức xảy ra khi và chỉ khi $a = b = c = 1$."
                )
                summary = "Hội đồng AI đã bổ sung điều kiện dấu bằng $a=b=c=1$ từ phản biện của Skeptic."
            else:
                latex_sol = "Phương trình có nghiệm: $$x = \\frac{-b \\pm \\sqrt{\\Delta}}{2a}$$ với $\\Delta = b^2 - 4ac \\ge 0$."
                summary = "Hội đồng đã xem xét và thống nhất bổ sung điều kiện căn thức từ phản biện của Skeptic."

            obj = JudgeOutput(
                consensus_status="consensus_reached",
                winning_solver="solver_a",
                final_latex_solution=latex_sol,
                executive_summary=summary,
                confidence_score=0.98,
                dissenting_opinions=[],
            )
            parsed = obj.model_dump()

        elif response_schema is SolverOutput or (response_schema is None and ("Chuyên gia Giải toán" in system_prompt or "Reviser" in system_prompt)):
            if ctx == "combinatorics_chessboard":
                summary = "Sử dụng phân hoạch đường chéo và nguyên lý Dirichlet để tìm số lượng quân tượng tối đa không ăn nhau trên bàn cờ N x N."
                claims = [
                    ClaimItem(label="C1", content="Trên bàn cờ $N \\times N$, mỗi quân tượng kiểm soát các ô trên các đường chéo. Có $2N - 1$ đường chéo song song theo mỗi hướng.", claim_type="definition", depends_on=[]),
                    ClaimItem(label="C2", content="Mỗi đường chéo chỉ chứa tối đa 1 quân tượng. Phân hoạch bàn cờ theo hệ đường chéo cùng hướng và đánh giá theo màu ô cờ, tổng số quân tượng không vượt quá $(N-1) + (N-1) = 2N - 2$ với $N \\ge 2$.", claim_type="inference", depends_on=["C1"]),
                    ClaimItem(label="C3", content="Chỉ ra cách đặt $2N - 2$ quân tượng thỏa mãn: đặt toàn bộ $N$ quân ở hàng 1 và $N-2$ quân ở hàng $N$ (bỏ 2 ô góc). Với $N=1$, đáp số là 1.", claim_type="calculation", depends_on=["C2"]),
                ]
                ans = "2N - 2 (với N >= 2), 1 (với N = 1)"
            elif ctx == "game_theory":
                summary = "Phân tích chiến lược chọn số của Alice và Bob trên tập S = {1, 2, ..., n}."
                claims = [
                    ClaimItem(label="C1", content="Tổng tất cả các số trong tập $S$ là $T = \\frac{n(n+1)}{2}$.", claim_type="definition", depends_on=[]),
                    ClaimItem(label="C2", content="Phân tích tính chẵn lẻ và phân loại trường hợp $n \\ge 4$ với $n \\le 3$.", claim_type="inference", depends_on=["C1"]),
                    ClaimItem(label="C3", content="Khi $n \\ge 4$, Alice luôn có thể ép tổng các số đã chọn là hợp số.", claim_type="calculation", depends_on=["C2"]),
                ]
                ans = "Alice thắng khi n >= 4; Bob thắng khi n in {1, 2, 3}"
            elif ctx == "geometry":
                summary = "Sử dụng hệ thức lượng và tính chất hình học tam giác."
                claims = [
                    ClaimItem(label="C1", content="Xét tam giác với các cạnh thỏa mãn định lý hình học.", claim_type="definition", depends_on=[]),
                    ClaimItem(label="C2", content="Áp dụng định lý Pythagoras và tỉ số lượng giác.", claim_type="inference", depends_on=["C1"]),
                    ClaimItem(label="C3", content="Thiết lập đẳng thức hình học cần chứng minh.", claim_type="calculation", depends_on=["C2"]),
                ]
                ans = "Đẳng thức hình học được chứng minh hoàn tất"
            elif ctx == "inequality":
                summary = "Sử dụng bất đẳng thức Cauchy-Schwarz để đánh giá biểu thức."
                claims = [
                    ClaimItem(label="C1", content="Áp dụng Cauchy-Schwarz: $\\frac{ab^2}{1+b^2} \\le \\frac{ab}{2}$.", claim_type="definition", depends_on=[]),
                    ClaimItem(label="C2", content="Suy ra $\\sum \\frac{a}{1+b^2} \\ge (a+b+c) - \\frac{ab+bc+ca}{2}$.", claim_type="inference", depends_on=["C1"]),
                    ClaimItem(label="C3", content="Do $ab+bc+ca \\le \\frac{(a+b+c)^2}{3} = 3$, biểu thức $\\ge 3 - 1.5 = \\frac{3}{2}$.", claim_type="calculation", depends_on=["C2"]),
                ]
                ans = "\\ge 3/2, dấu bằng khi a = b = c = 1"
            else:
                summary = "Sử dụng phương pháp biệt thức Delta để tìm nghiệm."
                claims = [
                    ClaimItem(label="C1", content="Xét biệt thức $\\Delta = b^2 - 4ac$.", claim_type="definition", depends_on=[]),
                    ClaimItem(label="C2", content="Biến đổi thành $(x + \\frac{b}{2a})^2 = \\frac{\\Delta}{4a^2}$.", claim_type="inference", depends_on=["C1"]),
                    ClaimItem(label="C3", content="Khai căn hai vế được nghiệm $x_{1,2} = \\frac{-b \\pm \\sqrt{\\Delta}}{2a}$.", claim_type="calculation", depends_on=["C2"]),
                ]
                ans = "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"

            obj = SolverOutput(
                summary=summary,
                claims=claims,
                final_answer=ans,
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
