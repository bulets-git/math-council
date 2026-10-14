import json
import os

benchmark_data = {
    "version": "1.0",
    "description": "Bộ dữ liệu kiểm thử Toán HSG/Olympiad & Bẫy ngụy biện cho Math Council",
    "problems": [
        {
            "code": "B01_FE_MISSING_CASE",
            "title": "Phương trình hàm hiệu bình phương (Bẫy chia cho 0)",
            "subject": "Đại số & Giải tích",
            "difficulty": "VMO / Quốc gia",
            "input_type": "text",
            "statement_original": "Tìm tất cả các hàm số $f: \\mathbb{R} \\to \\mathbb{R}$ thỏa mãn:\n$$f(x^2 - y^2) = x f(x) - y f(y), \\quad \\forall x, y \\in \\mathbb{R}$$",
            "mock_scenario": "fallacious_missing_case",
            "fallacious_solution": {
                "summary": "Chứng minh hàm cộng tính rồi rút gọn trực tiếp bằng phép chia.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Với mọi $x \\in \\mathbb{R}$, $f(x^2) = x f(x)$ và $f(-t) = -f(t)$.",
                        "reasoning": "Thay $y=0$ được $f(x^2) = xf(x)$. Hoán đổi vai trò $x, y$ suy ra $f$ là hàm lẻ.",
                        "depends_on": [],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Hàm số $f$ cộng tính trên toàn bộ $\\mathbb{R}$: $f(u+v) = f(u) + f(v)$.",
                        "reasoning": "Với $u, v \\ge 0$, đặt $x=\\sqrt{u}, y=\\sqrt{v}$ suy ra $f(u-v) = f(u)-f(v)$, kết hợp tính lẻ suy ra cộng tính trên $\\mathbb{R}$.",
                        "depends_on": ["C1"],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C3",
                        "statement": "Chia hai vế của phương trình hệ quả cho $(f(x) - x)$ ta thu được nghiệm duy nhất $f(x) = x$.",
                        "reasoning": "Biến đổi $f((x+1)^2 - x^2) = f(2x+1)$ rồi chia trực tiếp cho nhân tử $(f(x) - x)$.",
                        "depends_on": ["C1", "C2"],
                        "status": "unverified"
                    }
                ]
            },
            "expected_skeptic_challenge": {
                "target_claim_id": "C3",
                "error_type": "missing_case",
                "severity": "critical",
                "explanation": "Thực hiện phép chia cho biểu thức $(f(x) - x)$ khi chưa xét trường hợp biểu thức này bằng 0. Thực tế mọi hàm tuyến tính $f(x) = kx$ với $k \\in \\mathbb{R}$ bất kỳ đều thỏa mãn đề bài."
            }
        },
        {
            "code": "B02_NT_INVALID_LTE",
            "title": "Phương trình mũ Diophantine (Bẫy áp dụng sai LTE cho p=2)",
            "subject": "Số học",
            "difficulty": "Chuyên / Khu vực",
            "input_type": "text",
            "statement_original": "Tìm tất cả các cặp số nguyên dương $(n, k)$ sao cho:\n$$3^n + 1 = 2^k$$",
            "mock_scenario": "fallacious_invalid_inference",
            "fallacious_solution": {
                "summary": "Xét tính chẵn lẻ của $n$ và dùng trực tiếp công thức LTE của số nguyên tố lẻ cho $p=2$.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Nếu $n$ chẵn thì không tồn tại $k$ nguyên dương thỏa mãn.",
                        "reasoning": "Với $n=2m$, $3^{2m} + 1 \\equiv 2 \\pmod 4 \\implies 2^k \\equiv 2 \\pmod 4 \\implies k=1 \\implies 3^n = 1 \\implies n=0$ (mâu thuẫn).",
                        "depends_on": [],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Với $n$ lẻ, áp dụng Bổ đề nâng số mũ (LTE) cho $p=2$: $v_2(3^n + 1) = v_2(3+1) + v_2(n) = 2 + v_2(n) = 2$.",
                        "reasoning": "Do $2 \\mid (3+1)$ nên theo công thức LTE chuẩn $v_p(x^n+y^n) = v_p(x+y) + v_p(n)$, mặt khác $n$ lẻ nên $v_2(n)=0$.",
                        "depends_on": ["C1"],
                        "status": "unverified"
                    }
                ]
            },
            "expected_skeptic_challenge": {
                "target_claim_id": "C2",
                "error_type": "invalid_inference",
                "severity": "critical",
                "explanation": "Áp dụng sai định lý LTE cho $p=2$. Công thức $v_p(x^n+y^n) = v_p(x+y) + v_p(n)$ chỉ phát biểu dưới dạng đó cho số nguyên tố lẻ $p$. Với $p=2$ và $n$ lẻ, ta dùng phân tích $3^n+1 = (3+1)(3^{n-1} - 3^{n-2} + \\dots + 1)$ trong đó nhân tử thứ hai gồm $n$ số hạng lẻ nên là số lẻ, mới suy ra $v_2(3^n+1) = 2$."
            }
        },
        {
            "code": "B03_INEQ_FALSE_WLOG",
            "title": "Bất đẳng thức hoán vị (Bẫy giả sử thứ tự WLOG sai)",
            "subject": "Bất đẳng thức",
            "difficulty": "VMO / Quốc gia",
            "input_type": "text",
            "statement_original": "Cho các số thực dương $a, b, c$ thỏa mãn $a + b + c = 3$. Chứng minh rằng:\n$$\\frac{a}{1 + b^2} + \\frac{b}{1 + c^2} + \\frac{c}{1 + a^2} \\ge \\frac{3}{2}$$",
            "mock_scenario": "fallacious_invalid_inference",
            "fallacious_solution": {
                "summary": "Giả sử $a \\ge b \\ge c$ và áp dụng bất đẳng thức Chebyshev.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Không mất tính tổng quát (WLOG), giả sử $a \\ge b \\ge c > 0$.",
                        "reasoning": "Vai trò của các biến $a, b, c$ trong giả thiết $a+b+c=3$ là như nhau.",
                        "depends_on": [],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Áp dụng BĐT Chebyshev cho hai dãy cùng chiều ta có ĐPCM.",
                        "reasoning": "Ghép cặp trực tiếp tử số và mẫu số theo thứ tự giảm dần.",
                        "depends_on": ["C1"],
                        "status": "unverified"
                    }
                ]
            },
            "expected_skeptic_challenge": {
                "target_claim_id": "C1",
                "error_type": "invalid_inference",
                "severity": "critical",
                "explanation": "Biểu thức vế trái chỉ là tổng hoán vị vòng quanh (cyclic) chứ không đối xứng toàn phần (symmetric). Chỉ được phép giả sử $a = \\max\\{a,b,c\\}$, tuyệt đối không được giả sử $a \\ge b \\ge c$."
            }
        },
        {
            "code": "B04_COMB_UNSUPPORTED",
            "title": "Phủ bàn cờ bằng quân Domino cực tiểu (Bẫy khẳng định vô căn cứ)",
            "subject": "Tổ hợp",
            "difficulty": "VMO / TST",
            "input_type": "text",
            "statement_original": "Trên bàn cờ kích thước $2n \\times 2n$, người ta đặt một số quân domino $1 \\times 2$ hoặc $2 \\times 1$ không chồng lên nhau sao cho không thể đặt thêm bất kỳ quân domino nào nữa. Tìm giá trị nhỏ nhất của số quân domino đã được đặt.",
            "mock_scenario": "fallacious_unsupported_claim",
            "fallacious_solution": {
                "summary": "Dùng nhận xét trực quan về mật độ ô trống tối đa.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Hai ô trống bất kỳ không được kề cạnh nhau.",
                        "reasoning": "Nếu có hai ô trống kề cạnh thì ta có thể đặt thêm 1 quân domino vào hai ô đó.",
                        "depends_on": [],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Hiển nhiên tỷ lệ số quân domino tối thiểu chiếm đúng $\\frac{1}{3}$ diện tích bàn cờ trong mọi trường hợp.",
                        "reasoning": "Do cứ 1 quân domino (2 ô) thì khóa được tối đa 1 ô trống bên cạnh.",
                        "depends_on": ["C1"],
                        "status": "unverified"
                    }
                ]
            },
            "expected_skeptic_challenge": {
                "target_claim_id": "C2",
                "error_type": "unsupported_claim",
                "severity": "major",
                "explanation": "Khẳng định '1 quân domino khóa tối đa 1 ô trống' là vô căn cứ khi chưa đếm số cặp cạnh kề (double counting) giữa tập ô trống và tập ô bị phủ, đồng thời bỏ qua hiệu ứng tại biên của bàn cờ $2n \\times 2n$."
            }
        },
        {
            "code": "B05_GEO_AMBIGUOUS",
            "title": "Đường thẳng qua trực tâm vuông góc trung tuyến (Bẫy cấu hình hình học)",
            "subject": "Hình học",
            "difficulty": "VMO / Quốc gia",
            "input_type": "text",
            "statement_original": "Cho tam giác $ABC$ nhọn không cân nội tiếp đường tròn $(O)$, trực tâm $H$. Gọi $M$ là trung điểm của $BC$. Đường thẳng qua $H$ vuông góc với $MH$ cắt $AB, AC$ lần lượt tại $P, Q$. Chứng minh rằng $HP = HQ$.",
            "mock_scenario": "fallacious_ambiguous",
            "fallacious_solution": {
                "summary": "Biến đổi góc không định hướng thông qua chân đường cao.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Gọi $BE, CF$ là các đường cao của $\\triangle ABC$, khi đó $M$ là tâm đường tròn ngoại tiếp tứ giác $BCEF$.",
                        "reasoning": "$\\widehat{BEC} = \\widehat{BFC} = 90^\\circ$ và $M$ là trung điểm $BC$.",
                        "depends_on": [],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Tam giác $HPQ$ cân tại $H$ nên $HP = HQ$.",
                        "reasoning": "Cộng góc trực tiếp suy ra $\\widehat{HPQ} = \\widehat{HQP}$ mà không chứng minh hệ thức lượng qua trục đẳng phương hay định lý con bướm.",
                        "depends_on": ["C1"],
                        "status": "unverified"
                    }
                ]
            },
            "expected_skeptic_challenge": {
                "target_claim_id": "C2",
                "error_type": "needs_more_evidence",
                "severity": "critical",
                "explanation": "Từ $HP = HQ$ không thể suy ra bằng cách nói 'tam giác $HPQ$ cân tại $H$' vì $P, H, Q$ thẳng hàng ($H$ nằm trên đoạn $PQ$). Đây là lỗi ngụy biện hình học nghiêm trọng."
            }
        },
        {
            "code": "B06_POLY_CALC_ERROR",
            "title": "Ước nguyên tố của đa thức bậc 4 (Bẫy tính toán sai)",
            "subject": "Số học",
            "difficulty": "Chuyên / Khu vực",
            "input_type": "text",
            "statement_original": "Tìm tất cả các số nguyên tố $p$ sao cho tồn tại số nguyên dương $n$ thỏa mãn $p \\mid n^4 - n^2 + 1$.",
            "mock_scenario": "fallacious_calculation",
            "fallacious_solution": {
                "summary": "Sử dụng cấp của phần tử modulo $p$.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Nếu $p \\mid n^4 - n^2 + 1$ thì $n^{12} \\equiv 1 \\pmod p$.",
                        "reasoning": "Ta có $(n^2+1)(n^4-n^2+1) = n^6+1$, suy ra $n^6 \\equiv -1 \\pmod p \\implies n^{12} \\equiv 1 \\pmod p$.",
                        "depends_on": [],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Trong trường hợp $\\text{ord}_p(n) = 4$, ta suy ra $p = 5$.",
                        "reasoning": "Vì $n^4 \\equiv 1 \\pmod p$ nên $n^2 \\equiv 2 \\pmod p \\implies n^4 \\equiv 2^2 = 6 \\equiv 1 \\pmod p \\implies p = 5$.",
                        "depends_on": ["C1"],
                        "status": "unverified"
                    }
                ]
            },
            "expected_skeptic_challenge": {
                "target_claim_id": "C2",
                "error_type": "incorrect_calculation",
                "severity": "critical",
                "explanation": "Tính toán sai số học cơ bản: $2^2 = 4$ chứ không phải $6$. Từ $4 \\equiv 1 \\pmod p$ phải suy ra $p = 3$, không phải $p = 5$."
            }
        },
        {
            "code": "B07_DAG_CIRCULAR",
            "title": "Bất đẳng thức Nesbitt biến thể (Kịch bản kiểm tra Chu trình DAG)",
            "subject": "Bất đẳng thức",
            "difficulty": "Chuyên / Khu vực",
            "input_type": "text",
            "statement_original": "Cho các số thực dương $x, y, z$ thỏa mãn $xyz = 1$. Chứng minh rằng:\n$$\\frac{x^2}{y+z} + \\frac{y^2}{z+x} + \\frac{z^2}{x+y} \\ge \\frac{3}{2}$$",
            "mock_scenario": "dag_cycle_error",
            "fallacious_solution": {
                "summary": "Lời giải có các mệnh đề phụ thuộc vòng tròn C1 -> C3 -> C2 -> C1.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Tổng vế trái lớn hơn hoặc bằng $\\frac{x+y+z}{2}$.",
                        "reasoning": "Suy ra trực tiếp từ bổ đề ở C3.",
                        "depends_on": ["C3"],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Bất đẳng thức ban đầu đúng với mọi $x, y, z > 0, xyz = 1$.",
                        "reasoning": "Kết hợp C1 và AM-GM $x+y+z \\ge 3$.",
                        "depends_on": ["C1"],
                        "status": "unverified"
                    },
                    {
                        "claim_id": "C3",
                        "statement": "Bổ đề trung gian đúng.",
                        "reasoning": "Áp dụng chính kết quả ở C2 cho bộ biến hoán vị.",
                        "depends_on": ["C2"],
                        "status": "unverified"
                    }
                ]
            }
        },
        {
            "code": "B08_NEEDS_REVIEW_TYPO",
            "title": "Đề bài nghi ngờ chép sai dấu bất đẳng thức (Kiểm tra trạng thái needs_review)",
            "subject": "Bất đẳng thức",
            "difficulty": "Cơ bản",
            "input_type": "text",
            "statement_original": "Cho các số thực dương $a, b, c$ thỏa mãn $a + b + c = 3$. Chứng minh rằng:\n$$a^2 + b^2 + c^2 \\le 1$$",
            "mock_scenario": "needs_review_malformed"
        },
        {
            "code": "B09_VALID_IMO1959",
            "title": "IMO 1959 Bài 1 — Phân số tối giản (Kịch bản Lời giải Đúng chuẩn)",
            "subject": "Số học",
            "difficulty": "IMO / Quốc tế",
            "input_type": "text",
            "statement_original": "Chứng minh rằng với mọi số nguyên dương $n$, phân số sau đây là phân số tối giản:\n$$\\frac{21n + 4}{14n + 3}$$",
            "mock_scenario": "valid_complete_proof",
            "valid_solution": {
                "summary": "Sử dụng tổ hợp tuyến tính nguyên để triệt tiêu $n$ và tìm ước chung lớn nhất.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Với mọi số nguyên dương $n$, ta có đẳng thức $3(14n + 3) - 2(21n + 4) = 1$.",
                        "reasoning": "Khai triển trực tiếp: $3(14n+3) - 2(21n+4) = 42n + 9 - 42n - 8 = 1$.",
                        "depends_on": [],
                        "status": "supported"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Mọi ước chung nguyên dương $d$ của $21n+4$ và $14n+3$ đều phải là ước của $1$, suy ra $\\gcd(21n+4, 14n+3) = 1$.",
                        "reasoning": "Từ C1, nếu $d \\mid (21n+4)$ và $d \\mid (14n+3)$ thì $d \\mid [3(14n+3) - 2(21n+4)] = 1 \\implies d = 1$. Vậy phân số đã cho tối giản.",
                        "depends_on": ["C1"],
                        "status": "supported"
                    }
                ]
            }
        },
        {
            "code": "B10_VALID_PIGEONHOLE",
            "title": "Chọn số chia hết trong tập con của {1, 2, ..., 2n} (Kịch bản Lời giải Đúng chuẩn)",
            "subject": "Tổ hợp",
            "difficulty": "Chuyên / Khu vực",
            "input_type": "text",
            "statement_original": "Cho tập hợp $S = \\{1, 2, \\dots, 2n\\}$. Từ $S$ ta chọn ra $n+1$ số phân biệt bất kỳ. Chứng minh rằng trong các số được chọn, luôn tồn tại hai số sao cho số này là bội của số kia.",
            "mock_scenario": "valid_complete_proof",
            "valid_solution": {
                "summary": "Biểu diễn mỗi số dưới dạng $2^k \\cdot m$ với $m$ lẻ và áp dụng Nguyên lý Dirichlet.",
                "claims": [
                    {
                        "claim_id": "C1",
                        "statement": "Mỗi số nguyên dương $x \\in S$ đều viết được duy nhất dưới dạng $x = 2^k \\cdot m$, trong đó $k \\ge 0$ và $m$ là số nguyên dương lẻ thuộc tập $O = \\{1, 3, 5, \\dots, 2n-1\\}$.",
                        "reasoning": "Chia liên tiếp $x$ cho $2$ cho đến khi thu được thương là số lẻ $m \\le x \\le 2n$.",
                        "depends_on": [],
                        "status": "supported"
                    },
                    {
                        "claim_id": "C2",
                        "statement": "Tồn tại hai số được chọn $x_1 \\neq x_2$ có cùng phần lẻ $m$, từ đó số lớn hơn chia hết cho số nhỏ hơn.",
                        "reasoning": "Tập $O$ có đúng $n$ phần tử lẻ nhưng có $n+1$ số được chọn. Theo Nguyên lý Dirichlet, có hai số $x_1 = 2^{k_1}m$ và $x_2 = 2^{k_2}m$ ($k_1 < k_2$) có cùng phần lẻ $m$, suy ra $x_1 \\mid x_2$.",
                        "depends_on": ["C1"],
                        "status": "supported"
                    }
                ]
            }
        }
    ]
}

seed_script_content = '''"""
Script nạp nhanh 10 bài toán Olympic mẫu vào Math Council API.
Cách chạy (sau khi docker compose up):
    docker compose exec api python scripts/seed_problems.py
"""
import asyncio
import json
from pathlib import Path
import httpx

API_BASE_URL = "http://localhost:8000/api/v1"
FIXTURE_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "olympiad_benchmark_seed.json"


async def main() -> None:
    if not FIXTURE_PATH.exists():
        print(f"Không tìm thấy file fixture tại: {FIXTURE_PATH}")
        return

    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    problems = data.get("problems", [])

    async with httpx.AsyncClient(timeout=15.0) as client:
        print(f"Đang nạp {len(problems)} bài toán Olympic mẫu vào {API_BASE_URL}...")
        for item in problems:
            payload = {
                "title": f"[{item['code']}] {item['title']}",
                "statement_original": item["statement_original"],
                "input_type": item.get("input_type", "text"),
                "subject": item.get("subject"),
                "difficulty": item.get("difficulty"),
            }
            resp = await client.post(f"{API_BASE_URL}/problems", json=payload)
            if resp.status_code == 201:
                created = resp.json()
                print(f"  [201 CREATED] {created['title']} (ID: {created['id']})")
            else:
                print(f"  [ERROR {resp.status_code}] {item['code']}: {resp.text}")

    print("\\nHoàn tất nạp dữ liệu! Hãy mở http://localhost:3000 để xem danh sách bài toán.")


if __name__ == "__main__":
    asyncio.run(main())
'''


def main():
    fixture_dir = "math-council/services/api/tests/fixtures"
    scripts_dir = "math-council/services/api/scripts"
    os.makedirs(fixture_dir, exist_ok=True)
    os.makedirs(scripts_dir, exist_ok=True)

    fixture_file = os.path.join(fixture_dir, "olympiad_benchmark_seed.json")
    with open(fixture_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, ensure_ascii=False, indent=2)
    print(f"  [OK] Đã tạo bộ dữ liệu Benchmark: {fixture_file}")

    seed_file = os.path.join(scripts_dir, "seed_problems.py")
    with open(seed_file, "w", encoding="utf-8") as f:
        f.write(seed_script_content)
    print(f"  [OK] Đã tạo script nạp dữ liệu tự động: {seed_file}")


if __name__ == "__main__":
    main()