"""
Script nạp nhanh 10 bài toán Olympic mẫu vào Math Council API.
Cách chạy: docker compose exec api python scripts/seed_problems.py
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
                print(f"  [201 CREATED] {payload['title']}")
            else:
                print(f"  [ERROR {resp.status_code}] {item['code']}: {resp.text}")


if __name__ == "__main__":
    asyncio.run(main())
