import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_200(client: AsyncClient):
    """GET /health trả về 200 OK và thông tin trạng thái DB."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("database") == "connected"


@pytest.mark.asyncio
async def test_create_problem_with_vietnamese_latex(client: AsyncClient):
    """POST /api/v1/problems với đề toán chứa công thức LaTeX tiếng Việt.

    Phải trả về 201 Created và giữ nguyên vẹn chuỗi LaTeX trong statement_original.
    """
    vietnamese_latex_statement = (
        "Cho hình lăng trụ đứng $ABC.A'B'C'$ có đáy $ABC$ là tam giác vuông tại $B$, "
        "$AB = a$, $BC = a\\sqrt{3}$. Góc giữa đường thẳng $A'C$ và mặt phẳng $(ABC)$ "
        "bằng $60^\\circ$.\n"
        "1. Tính thể tích khối lăng trụ theo công thức: "
        "$$V = B \\cdot h = \\frac{1}{2} a^2 \\sqrt{3} \\cdot a\\sqrt{3} \\tan(60^\\circ) = \\frac{9}{2} a^3$$\n"
        "2. Tìm tập nghiệm của bất phương trình: $\\log_2(x^2 - 3x + 2) \\le 1$."
    )

    payload = {
        "title": "Bài toán hình không gian và logarit lớp 12",
        "statement_original": vietnamese_latex_statement,
        "input_type": "text",
        "subject": "Hình học & Giải tích",
        "difficulty": "Vận dụng",
    }

    response = await client.post("/api/v1/problems", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["title"] == payload["title"]
    assert data["statement_original"] == vietnamese_latex_statement
    assert data["input_type"] == "text"
    assert data["subject"] == payload["subject"]
    assert data["difficulty"] == payload["difficulty"]
    assert "id" in data
    assert "created_at" in data
    assert data["runs"] == []


@pytest.mark.asyncio
async def test_create_problem_validation_error_empty_or_whitespace(client: AsyncClient):
    """POST /api/v1/problems với chuỗi rỗng "" hoặc chỉ có dấu cách "   \\n\\t "

    phải trả về 422 Unprocessable Entity.
    """
    # 1. Chuỗi rỗng
    res_empty = await client.post(
        "/api/v1/problems",
        json={"title": "Đề rỗng", "statement_original": ""},
    )
    assert res_empty.status_code == 422

    # 2. Toàn khoảng trắng, xuống dòng, tab
    res_whitespace = await client.post(
        "/api/v1/problems",
        json={"title": "Đề toàn khoảng trắng", "statement_original": "   \n\t "},
    )
    assert res_whitespace.status_code == 422

    # 3. Thiếu trường statement_original
    res_missing = await client.post(
        "/api/v1/problems",
        json={"title": "Thiếu đề"},
    )
    assert res_missing.status_code == 422


@pytest.mark.asyncio
async def test_get_problems_list_and_detail(client: AsyncClient):
    """GET /api/v1/problems và GET /api/v1/problems/{id} trả về đúng bài toán vừa tạo."""
    statement = "Tìm giá trị lớn nhất của hàm số $f(x) = -x^2 + 4x - 3$ trên đoạn $[0, 3]$."
    create_payload = {
        "title": "Cực trị hàm số",
        "statement_original": statement,
        "subject": "Giải tích 12",
        "difficulty": "Cơ bản",
    }

    create_res = await client.post("/api/v1/problems", json=create_payload)
    assert create_res.status_code == 201
    created_problem = create_res.json()
    problem_id = created_problem["id"]

    # 1. Kiểm tra GET /api/v1/problems
    list_res = await client.get("/api/v1/problems")
    assert list_res.status_code == 200
    problems_list = list_res.json()
    assert len(problems_list) >= 1

    matched = next((p for p in problems_list if p["id"] == problem_id), None)
    assert matched is not None
    assert matched["title"] == create_payload["title"]
    assert matched["statement_original"] == statement
    assert matched["latest_run_status"] is None

    # 2. Kiểm tra GET /api/v1/problems/{id}
    detail_res = await client.get(f"/api/v1/problems/{problem_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == problem_id
    assert detail_data["title"] == create_payload["title"]
    assert detail_data["statement_original"] == statement
    assert detail_data["runs"] == []


@pytest.mark.asyncio
async def test_create_run_for_problem_returns_202_queued(client: AsyncClient):
    """POST /api/v1/problems/{id}/runs trả về 202 Accepted với status == "queued"."""
    # Tạo trước 1 bài toán
    create_res = await client.post(
        "/api/v1/problems",
        json={"statement_original": "Giải hệ phương trình $\\begin{cases} x + y = 3 \\\\ x - y = 1 \\end{cases}$"},
    )
    assert create_res.status_code == 201
    problem_id = create_res.json()["id"]

    # Tạo Run cho bài toán
    run_payload = {
        "budget_usd": 2.50,
        "config": {
            "mode": "step2_skeleton",
            "ai_enabled": False,
            "max_rounds": 2,
        },
    }
    run_res = await client.post(f"/api/v1/problems/{problem_id}/runs", json=run_payload)
    assert run_res.status_code == 202
    run_data = run_res.json()

    assert run_data["status"] == "queued"
    assert run_data["problem_id"] == problem_id
    assert float(run_data["budget_usd"]) == 2.50
    assert run_data["ai_notice"] == "Chưa chạy AI (Bước 2)"
    assert "id" in run_data
    assert "created_at" in run_data


@pytest.mark.asyncio
async def test_get_run_by_id_returns_200_and_queued_status(client: AsyncClient):
    """GET /api/v1/runs/{id} trả về 200 OK và đúng trạng thái queued."""
    # 1. Tạo bài toán
    p_res = await client.post(
        "/api/v1/problems",
        json={"statement_original": "Tính $\\int_0^\\pi \\sin(x) dx$"},
    )
    assert p_res.status_code == 201
    problem_id = p_res.json()["id"]

    # 2. Tạo run
    run_res = await client.post(f"/api/v1/problems/{problem_id}/runs", json={})
    assert run_res.status_code == 202
    run_id = run_res.json()["id"]

    # 3. GET /api/v1/runs/{id}
    get_run_res = await client.get(f"/api/v1/runs/{run_id}")
    assert get_run_res.status_code == 200
    run_detail = get_run_res.json()
    assert run_detail["id"] == run_id
    assert run_detail["problem_id"] == problem_id
    assert run_detail["status"] == "queued"
    assert run_detail["ai_notice"] == "Chưa chạy AI (Bước 2)"

    # 4. Kiểm tra danh sách bài toán cập nhật latest_run_status
    list_res = await client.get("/api/v1/problems")
    assert list_res.status_code == 200
    matched = next((p for p in list_res.json() if p["id"] == problem_id), None)
    assert matched is not None
    assert matched["latest_run_status"] == "queued"

    # 5. Kiểm tra chi tiết bài toán chứa run vừa tạo
    p_detail_res = await client.get(f"/api/v1/problems/{problem_id}")
    assert p_detail_res.status_code == 200
    p_detail = p_detail_res.json()
    assert len(p_detail["runs"]) == 1
    assert p_detail["runs"][0]["id"] == run_id


@pytest.mark.asyncio
async def test_non_existent_uuid_returns_404(client: AsyncClient):
    """Gọi GET /api/v1/problems/{random_uuid}, POST /api/v1/problems/{random_uuid}/runs,

    và GET /api/v1/runs/{random_uuid} với UUID không tồn tại đều phải trả về 404 Not Found.
    """
    random_uuid = str(uuid.uuid4())

    # 1. GET /api/v1/problems/{random_uuid}
    get_prob_res = await client.get(f"/api/v1/problems/{random_uuid}")
    assert get_prob_res.status_code == 404

    # 2. POST /api/v1/problems/{random_uuid}/runs
    post_run_res = await client.post(
        f"/api/v1/problems/{random_uuid}/runs",
        json={"budget_usd": 1.0},
    )
    assert post_run_res.status_code == 404

    # 3. GET /api/v1/runs/{random_uuid}
    get_run_res = await client.get(f"/api/v1/runs/{random_uuid}")
    assert get_run_res.status_code == 404
