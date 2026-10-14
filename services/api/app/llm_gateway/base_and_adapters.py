import abc
import json
import logging
import re
import time
from decimal import Decimal
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger("llm_gateway.base_and_adapters")
from app.schemas.agent_contracts import (
    ChallengeAdjudicationItemSchema,
    ChallengeItemSchema,
    ClaimItemSchema,
    JudgeOutputSchema,
    NormalizationOutputSchema,
    ProofStepSchema,
    SkepticOutputSchema,
    SolverOutputSchema,
    SolverRevisionOutputSchema,
    SourceDiscoveryOutputSchema,
    SourceMetadataSchema,
)

T = TypeVar("T", bound=BaseModel)

MODEL_PRICING_PER_1M: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-2.5-flash": (Decimal("0.15"), Decimal("0.60")),
    "gemini-2.5-pro": (Decimal("1.25"), Decimal("5.00")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "o3-mini": (Decimal("1.10"), Decimal("4.40")),
    "openai/o3-mini": (Decimal("1.10"), Decimal("4.40")),
    "claude-3-7-sonnet-latest": (Decimal("3.00"), Decimal("15.00")),
    "deepseek-chat": (Decimal("0.27"), Decimal("1.10")),
    "deepseek/deepseek-chat": (Decimal("0.27"), Decimal("1.10")),
    "deepseek-reasoner": (Decimal("0.55"), Decimal("2.19")),
    "deepseek/deepseek-reasoner": (Decimal("0.55"), Decimal("2.19")),
}


def calculate_call_cost(model_name: str, input_tokens: int, output_tokens: int) -> Decimal:
    in_price, out_price = MODEL_PRICING_PER_1M.get(
        model_name, (Decimal("1.00"), Decimal("3.00"))
    )
    cost = (Decimal(input_tokens) * in_price + Decimal(output_tokens) * out_price) / Decimal("1000000")
    return cost.quantize(Decimal("0.000001"))


def extract_json_object(raw_text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace : last_brace + 1]
    return cleaned


def build_schema_instruction(system_prompt: str, response_schema: type[BaseModel]) -> str:
    schema_json = json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
    return (
        f"{system_prompt}\n\n"
        "BẮT BUỘC: Chỉ trả về một đối tượng JSON hợp lệ duy nhất tuân thủ JSON Schema sau:\n"
        f"{schema_json}"
    )


class LLMCallResult(BaseModel):
    parsed_data: dict[str, Any]
    provider: str
    model_name: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_ms: int
    provider_request_id: str | None = None
    reasoning_content: str | None = None


class BaseLLMAdapter(abc.ABC):
    provider_name: str = "base"

    @abc.abstractmethod
    async def generate_structured(
        self,
        *,
        model_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        raise NotImplementedError


class OpenAIAdapter(BaseLLMAdapter):
    provider_name = "openai"

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = base_url.rstrip("/")

    async def generate_structured(
        self,
        *,
        model_name: str = "gpt-4o",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        if not self.api_key:
            logger.error("Thiếu API Key cho provider '%s' (base_url: %s)", self.provider_name, self.base_url)
            raise RuntimeError(f"Thiếu API Key cho provider '{self.provider_name}'.")

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        # deepseek-reasoner does not support response_format json_object
        if not any(k in model_name.lower() for k in ["reasoner", "o1"]):
            payload["response_format"] = {"type": "json_object"}

        # Reasoning models (o1, o3, o3-mini, deepseek-reasoner) do not accept custom temperature in OpenAI/DeepSeek APIs
        if not any(k in model_name.lower() for k in ["o1", "o3", "reasoner"]):
            payload["temperature"] = 0.2

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mathcouncil.ai",
            "X-Title": "Math Council Olympiad AI",
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.error(
                    "OpenAIAdapter HTTP Error %d from %s/chat/completions for model '%s': %s",
                    resp.status_code,
                    self.base_url,
                    model_name,
                    resp.text,
                )
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        choice = data["choices"][0]["message"]
        raw_content = choice.get("content") or ""
        reasoning_content = choice.get("reasoning_content") or ""

        # Extract reasoning from <think>...</think> if not in reasoning_content field
        if not reasoning_content and "<think>" in raw_content:
            think_match = re.search(r"<think>(.*?)</think>", raw_content, flags=re.DOTALL)
            if think_match:
                reasoning_content = think_match.group(1).strip()

        json_str = extract_json_object(raw_content)
        parsed_dict = json.loads(json_str)

        # Bóc tách reasoning tokens / thinking content vào lời giải
        if reasoning_content and isinstance(parsed_dict, dict):
            parsed_dict["reasoning_content"] = reasoning_content
            if "summary" in parsed_dict and "Tư duy suy luận" not in str(parsed_dict["summary"]):
                parsed_dict["summary"] = (
                    f"**[Tư duy suy luận (DeepSeek Reasoner)]**:\n{reasoning_content}\n\n"
                    f"**[Tóm tắt phương pháp]**:\n{parsed_dict['summary']}"
                )

        validated = response_schema.model_validate(parsed_dict)

        usage = data.get("usage", {})
        in_tok = int(usage.get("prompt_tokens", 0))
        out_tok = int(usage.get("completion_tokens", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
            provider_request_id=data.get("id"),
            reasoning_content=reasoning_content or None,
        )


class OpenAICompatibleAdapter(OpenAIAdapter):
    provider_name = "openai_compatible"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        super().__init__(
            api_key=api_key if api_key is not None else settings.OPENAI_COMPATIBLE_API_KEY,
            base_url=base_url if base_url is not None else settings.OPENAI_COMPATIBLE_BASE_URL,
        )


class AlibabaAdapter(OpenAICompatibleAdapter):
    provider_name = "alibaba"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        import os
        key = (
            api_key
            if api_key is not None
            else (os.getenv("ALIBABA_API_KEY") or getattr(settings, "ALIBABA_API_KEY", ""))
        )
        url = (
            base_url
            if base_url is not None
            else (
                os.getenv("ALIBABA_BASE_URL")
                or getattr(
                    settings,
                    "ALIBABA_BASE_URL",
                    "https://ws-dgcpkbso457jl8mu.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
                )
            )
        )
        super().__init__(api_key=key, base_url=url)


class DeepInfraAdapter(OpenAICompatibleAdapter):
    provider_name = "deepinfra"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        import os
        key = (
            api_key
            if api_key is not None
            else (os.getenv("DEEPINFRA_API_KEY") or getattr(settings, "DEEPINFRA_API_KEY", ""))
        )
        url = (
            base_url
            if base_url is not None
            else (
                os.getenv("DEEPINFRA_BASE_URL")
                or getattr(settings, "DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai")
            )
        )
        super().__init__(api_key=key, base_url=url)


class AnthropicAdapter(BaseLLMAdapter):
    provider_name = "anthropic"

    async def generate_structured(
        self,
        *,
        model_name: str = "claude-3-7-sonnet-latest",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        api_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"Chưa cấu hình ANTHROPIC_API_KEY cho model '{model_name}'. "
                "Vui lòng thiết lập biến môi trường ANTHROPIC_API_KEY trên Railway Variables."
            )

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        payload = {
            "model": model_name,
            "max_tokens": 4096,
            "temperature": 0.2,
            "system": full_system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.error("AnthropicAdapter HTTP Error %d for model '%s': %s", resp.status_code, model_name, resp.text)
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_text = data["content"][0]["text"]
        validated = response_schema.model_validate_json(extract_json_object(raw_text))

        usage = data.get("usage", {})
        in_tok = int(usage.get("input_tokens", 0))
        out_tok = int(usage.get("output_tokens", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
            provider_request_id=data.get("id"),
        )


class GeminiAdapter(BaseLLMAdapter):
    provider_name = "gemini"

    async def generate_structured(
        self,
        *,
        model_name: str = "gemini-2.5-pro",
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"Chưa cấu hình GEMINI_API_KEY cho model '{model_name}'. "
                "Vui lòng thiết lập biến môi trường GEMINI_API_KEY trên Railway Variables."
            )

        full_system_prompt = build_schema_instruction(system_prompt, response_schema)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": full_system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(url, params={"key": api_key}, json=payload)
            if resp.status_code >= 400:
                logger.error("GeminiAdapter HTTP Error %d for model '%s': %s", resp.status_code, model_name, resp.text)
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        validated = response_schema.model_validate_json(extract_json_object(raw_text))

        usage = data.get("usageMetadata", {})
        in_tok = int(usage.get("promptTokenCount", 0))
        out_tok = int(usage.get("candidatesTokenCount", 0))

        return validated, LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
        )

    async def generate_with_grounding(
        self,
        *,
        model_name: str = "gemini-2.5-flash",
        system_prompt: str,
        user_prompt: str,
        timeout_sec: float = 12.0,
    ) -> tuple[dict[str, Any], LLMCallResult]:
        api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"Chưa cấu hình GEMINI_API_KEY cho model '{model_name}'. "
                "Vui lòng thiết lập biến môi trường GEMINI_API_KEY trên Railway Variables."
            )

        start = time.perf_counter()
        summary = ""
        reference_urls: list[str] = []
        in_tok = 0
        out_tok = 0
        raw_grounding: dict[str, Any] = {}

        sdk_success = False
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[{"google_search": {}}],
                temperature=0.2,
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=config,
                ),
                timeout=timeout_sec,
            )
            if response.candidates:
                cand = response.candidates[0]
                if cand.content and cand.content.parts:
                    summary = "".join([p.text for p in cand.content.parts if getattr(p, "text", None)]).strip()
                elif hasattr(response, "text") and response.text:
                    summary = (response.text or "").strip()

                gm = getattr(cand, "grounding_metadata", None)
                if gm:
                    chunks = getattr(gm, "grounding_chunks", None) or []
                    for chunk in chunks:
                        web = getattr(chunk, "web", None)
                        if web:
                            uri = getattr(web, "uri", None)
                            if uri and uri not in reference_urls:
                                reference_urls.append(uri)
                    try:
                        raw_grounding = gm.model_dump() if hasattr(gm, "model_dump") else {}
                    except Exception:
                        pass
            elif hasattr(response, "text") and response.text:
                summary = response.text.strip()

            usage = getattr(response, "usage_metadata", None)
            if usage:
                in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
                out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
            sdk_success = True
        except asyncio.TimeoutError:
            raise
        except Exception as sdk_err:
            logger.warning(
                "Google GenAI SDK gặp lỗi (%s: %s). Thử kết nối trực tiếp qua REST API với tools=[{'google_search': {}}]...",
                type(sdk_err).__name__,
                sdk_err,
            )

        if not sdk_success:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.2},
            }
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(url, params={"key": api_key}, json=payload)
                if resp.status_code >= 400:
                    logger.error("GeminiAdapter HTTP Error %d for model '%s': %s", resp.status_code, model_name, resp.text)
                resp.raise_for_status()
                data = resp.json()

            candidates = data.get("candidates", [])
            if candidates:
                cand = candidates[0]
                parts = cand.get("content", {}).get("parts", [])
                summary = "".join([p.get("text", "") for p in parts]).strip()
                gm = cand.get("groundingMetadata", {})
                raw_grounding = gm
                for chunk in gm.get("groundingChunks", []):
                    web = chunk.get("web", {})
                    uri = web.get("uri")
                    if uri and uri not in reference_urls:
                        reference_urls.append(uri)

            usage = data.get("usageMetadata", {})
            in_tok = int(usage.get("promptTokenCount", 0))
            out_tok = int(usage.get("candidatesTokenCount", 0))

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        result = {
            "summary": summary,
            "reference_urls": reference_urls,
            "grounding_metadata": raw_grounding,
        }
        meta = LLMCallResult(
            parsed_data={"summary": summary, "reference_urls": reference_urls},
            provider=self.provider_name,
            model_name=model_name,
            prompt_version="grounding_v1",
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=calculate_call_cost(model_name, in_tok, out_tok),
            latency_ms=elapsed_ms,
        )
        return result, meta


class DeterministicMockAdapter(BaseLLMAdapter):
    provider_name = "mock"

    async def generate_structured(
        self,
        *,
        model_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 60.0,
    ) -> tuple[T, LLMCallResult]:
        start = time.perf_counter()

        if response_schema is NormalizationOutputSchema:
            needs_review = r"a^2 + b^2 + c^2 \le 1" in user_prompt or "NEEDS_REVIEW" in user_prompt
            subj = "Toán Olympic"
            p_lower = user_prompt.lower()
            if any(k in p_lower for k in ["bàn cờ", "quân tượng", "quân hậu", "quân mã", "tổ hợp", "rời rạc", "lưới ô vuông", "đồ thị", "dirichlet", "pigeonhole", "đường chéo", "bishop", "chessboard"]):
                subj = "Tổ hợp / Toán rời rạc"
            elif any(k in p_lower for k in ["ước số", "chia hết", "đồng dư", "nguyên tố", "nghiệm nguyên", "gcd", "21n + 4"]):
                subj = "Số học"
            elif any(k in p_lower for k in ["tam giác", "đường tròn", "hình học", "góc"]):
                subj = "Hình học"
            elif any(k in p_lower for k in ["bất đẳng thức", "am-gm", "cauchy"]):
                subj = "Bất đẳng thức"
            obj = NormalizationOutputSchema(
                statement_normalized=user_prompt.strip(),
                needs_clarification=needs_review,
                clarification_reason=(
                    "Đề bài có dấu hiệu chép sai chiều bất đẳng thức: với a=b=c=1 thì a^2+b^2+c^2 = 3 > 1."
                    if needs_review
                    else None
                ),
                detected_subject=subj,
            )
        elif response_schema is SolverOutputSchema:
            obj = SolverOutputSchema(
                task_type="solve",
                status="completed",
                summary="Biến đổi tương đương và sử dụng tính chất chia hết / bất đẳng thức cổ điển.",
                claims=[
                    ClaimItemSchema(
                        claim_id="C1",
                        statement="Thiết lập đẳng thức cơ sở hoặc điều kiện biên của bài toán.",
                        reasoning="Biến đổi đại số trực tiếp từ giả thiết đề bài.",
                        depends_on=[],
                        status="unverified",
                    ),
                    ClaimItemSchema(
                        claim_id="C2",
                        statement="Suy ra kết luận của bài toán từ mệnh đề C1.",
                        reasoning="Kết hợp C1 và tính chất số nguyên / bất đẳng thức.",
                        depends_on=["C1"],
                        status="unverified",
                    ),
                ],
                proof_steps=[
                    ProofStepSchema(step_id="S1", claim_refs=["C1"], content="Bước 1: Thiết lập bổ đề C1."),
                    ProofStepSchema(step_id="S2", claim_refs=["C1", "C2"], content="Bước 2: Hoàn tất chứng minh C2."),
                ],
                unresolved_questions=[],
                confidence="high",
            )
        elif response_schema is SkepticOutputSchema:
            if "21n + 4" in user_prompt:
                obj = SkepticOutputSchema(
                    overall_assessment="Lời giải chặt chẽ, tổ hợp tuyến tính đúng.",
                    challenges=[],
                    confidence="high",
                )
            else:
                obj = SkepticOutputSchema(
                    overall_assessment="Cần làm rõ điều kiện biên ở bước suy luận C2.",
                    challenges=[
                        ChallengeItemSchema(
                            target_claim_id="C2",
                            error_type="missing_case",
                            severity="major",
                            explanation="Chưa kiểm tra trường hợp biên khi mẫu số hoặc nhân tử triệt tiêu bằng 0.",
                            counterexample="Thử với giá trị biên x = y hoặc n = 1.",
                            required_fix="Bổ sung xét riêng trường hợp suy biến trước khi chia.",
                        )
                    ],
                    confidence="high",
                )
        elif response_schema is SolverRevisionOutputSchema:
            revised = SolverOutputSchema(
                task_type="revise",
                status="completed",
                summary="Đã bổ sung xét trường hợp biên theo phản biện của Skeptic.",
                claims=[
                    ClaimItemSchema(
                        claim_id="C1",
                        statement="Xét trường hợp biên suy biến, đẳng thức luôn thỏa mãn.",
                        reasoning="Thay trực tiếp giá trị biên vào phương trình gốc.",
                        depends_on=[],
                        status="supported",
                    ),
                    ClaimItemSchema(
                        claim_id="C2",
                        statement="Với trường hợp khác 0, thực hiện phép biến đổi tương đương suy ra ĐPCM.",
                        reasoning="Vì đã loại trừ trường hợp bằng 0 ở C1 nên phép chia hoàn toàn hợp lệ.",
                        depends_on=["C1"],
                        status="supported",
                    ),
                ],
                proof_steps=[
                    ProofStepSchema(step_id="S1", claim_refs=["C1", "C2"], content="Chứng minh đầy đủ cả 2 trường hợp.")
                ],
                confidence="high",
            )
            obj = SolverRevisionOutputSchema(
                revised_solution=revised,
                challenge_responses=[
                    {
                        "target_claim_id": "C2",
                        "action": "revised",
                        "response_explanation": "Đã tách trường hợp mẫu bằng 0 thành mệnh đề C1 riêng biệt.",
                    }
                ],
            )
        elif response_schema is JudgeOutputSchema:
            obj = JudgeOutputSchema(
                verdict_status="supported",
                selected_solver_role="solver_a",
                summary="Lời giải sau khi chỉnh sửa đã lấp đầy lỗ hổng xét trường hợp biên.",
                final_proof_markdown="### Lời giải tổng hợp\n1. Xét trường hợp biên (Mệnh đề C1).\n2. Xét trường hợp tổng quát (Mệnh đề C2).",
                challenge_adjudications=[
                    ChallengeAdjudicationItemSchema(
                        target_claim_id="C2",
                        new_status="accepted",
                        reason="Solver đã bổ sung mệnh đề C1 giải quyết triệt để trường hợp chia cho 0.",
                    )
                ],
                accepted_claims=["C1", "C2"],
                unresolved_issues=[],
            )
        elif response_schema is SourceDiscoveryOutputSchema:
            if "21n + 4" in user_prompt and "14n + 3" in user_prompt:
                canonical = SolverOutputSchema(
                    summary="Chứng minh phân số tối giản bằng thuật toán Euclid và tổ hợp tuyến tính triệt tiêu n.",
                    claims=[
                        ClaimItemSchema(
                            claim_id="C1",
                            statement="Gọi d = gcd(21n + 4, 14n + 3) với d là số nguyên dương.",
                            reasoning="Định nghĩa ước chung lớn nhất của tử số và mẫu số.",
                            depends_on=[],
                            status="supported",
                        ),
                        ClaimItemSchema(
                            claim_id="C2",
                            statement="Ta có d chia hết cho 2(21n + 4) - 3(14n + 3) = 42n + 8 - 42n - 9 = -1.",
                            reasoning="Tính chất tổ hợp tuyến tính triệt tiêu biến n: d | (2A - 3B).",
                            depends_on=["C1"],
                            status="supported",
                        ),
                        ClaimItemSchema(
                            claim_id="C3",
                            statement="Vì d | 1 và d > 0 nên d = 1. Phân số (21n + 4)/(14n + 3) tối giản với mọi số tự nhiên n.",
                            reasoning="Ước chung lớn nhất bằng 1 nên tử và mẫu nguyên tố cùng nhau.",
                            depends_on=["C2"],
                            status="supported",
                        ),
                    ],
                    proof_steps=[
                        ProofStepSchema(step_id="S1", claim_refs=["C1"], content="Đặt d = (21n + 4, 14n + 3)."),
                        ProofStepSchema(step_id="S2", claim_refs=["C2"], content="Xét 2(21n + 4) - 3(14n + 3) = -1 chia hết cho d."),
                        ProofStepSchema(step_id="S3", claim_refs=["C3"], content="Suy ra d = 1, phân số tối giản (đpcm)."),
                    ],
                    unresolved_questions=[],
                    confidence="high",
                )
                obj = SourceDiscoveryOutputSchema(
                    match_type="exact_match",
                    source_found=True,
                    source_metadata=SourceMetadataSchema(
                        competition_name="International Mathematical Olympiad (IMO)",
                        year=1959,
                        problem_number="Problem 1",
                        reference_urls=["https://artofproblemsolving.com/community/c6h54829"],
                    ),
                    variant_warning=None,
                    canonical_solution=canonical,
                )
            elif "21n" in user_prompt or "14n" in user_prompt:
                obj = SourceDiscoveryOutputSchema(
                    match_type="modified_variant",
                    source_found=True,
                    source_metadata=SourceMetadataSchema(
                        competition_name="International Mathematical Olympiad (IMO)",
                        year=1959,
                        problem_number="Problem 1 (Variant)",
                        reference_urls=["https://artofproblemsolving.com/community/c6h54829"],
                    ),
                    variant_warning="Đề bài có cấu trúc tương tự IMO 1959 Problem 1 nhưng các hệ số đã bị thay đổi.",
                    canonical_solution=None,
                )
            else:
                obj = SourceDiscoveryOutputSchema(
                    match_type="no_match",
                    source_found=False,
                    source_metadata=None,
                    variant_warning=None,
                    canonical_solution=None,
                )
        else:
            raise ValueError(f"Unsupported schema in MockAdapter: {response_schema}")

        elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
        validated = response_schema.model_validate(obj.model_dump())
        meta = LLMCallResult(
            parsed_data=validated.model_dump(),
            provider=self.provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            input_tokens=250,
            output_tokens=180,
            cost_usd=Decimal("0.001500"),
            latency_ms=elapsed_ms,
            provider_request_id="mock-req-001",
        )
        return validated, meta

    async def generate_with_grounding(
        self,
        *,
        model_name: str = "mock",
        system_prompt: str,
        user_prompt: str,
        timeout_sec: float = 12.0,
    ) -> tuple[dict[str, Any], LLMCallResult]:
        res = {
            "summary": "Mock Grounding: Bài toán số học/tổ hợp được tìm thấy trên cộng đồng AoPS từ các kỳ thi Olympic.",
            "reference_urls": [
                "https://artofproblemsolving.com/community",
                "https://en.wikipedia.org/wiki/International_Mathematical_Olympiad",
            ],
            "grounding_metadata": {},
        }
        meta = LLMCallResult(
            parsed_data=res,
            provider=self.provider_name,
            model_name=model_name,
            prompt_version="mock_grounding_v1",
            input_tokens=100,
            output_tokens=60,
            cost_usd=Decimal("0.000000"),
            latency_ms=10,
            provider_request_id="mock-grounding-001",
        )
        return res, meta


class MultiProviderRouter:
    def __init__(self, force_mock: bool | None = None) -> None:
        import os
        deepseek_base = os.getenv(
            "DEEPSEEK_BASE_URL", getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        ).rstrip("/")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", ""))

        if force_mock is not None:
            self.force_mock = force_mock
        else:
            self.force_mock = (settings.DEFAULT_LLM_PROVIDER == "mock")
        deepseek_adapter = OpenAIAdapter(api_key=deepseek_key, base_url=deepseek_base)
        deepseek_adapter.provider_name = "deepseek"

        self.adapters: dict[str, BaseLLMAdapter] = {
            "mock": DeterministicMockAdapter(),
            "gemini": GeminiAdapter(),
            "alibaba": AlibabaAdapter(),
            "deepseek": deepseek_adapter,
            "deepinfra": DeepInfraAdapter(),
        }

    def resolve_spec(self, role_model_spec: str) -> tuple[BaseLLMAdapter, str]:
        if self.force_mock or role_model_spec.startswith("mock:"):
            model_part = role_model_spec.split(":", 1)[1] if ":" in role_model_spec else role_model_spec
            return self.adapters["mock"], model_part

        if ":" in role_model_spec:
            provider_key, model_name = role_model_spec.split(":", 1)
        else:
            provider_key, model_name = settings.DEFAULT_LLM_PROVIDER, role_model_spec

        import os

        # 1. Google Gemini
        if provider_key == "gemini":
            gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
            if not gemini_key and not self.force_mock:
                raise ValueError(
                    f"Chưa cấu hình GEMINI_API_KEY cho model '{model_name}'. "
                    "Vui lòng thiết lập biến môi trường GEMINI_API_KEY trên Railway Variables."
                )
            return self.adapters["gemini"], model_name

        # 2. Alibaba Cloud MaaS
        if provider_key == "alibaba":
            alibaba_base = os.getenv(
                "ALIBABA_BASE_URL",
                getattr(
                    settings,
                    "ALIBABA_BASE_URL",
                    "https://ws-dgcpkbso457jl8mu.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
                ),
            ).rstrip("/")
            alibaba_key = os.getenv("ALIBABA_API_KEY", getattr(settings, "ALIBABA_API_KEY", ""))
            if not alibaba_key and not self.force_mock:
                raise ValueError(
                    f"Chưa cấu hình ALIBABA_API_KEY cho model '{model_name}'. "
                    "Vui lòng thiết lập biến môi trường ALIBABA_API_KEY trên Railway Variables."
                )
            adapter = AlibabaAdapter(api_key=alibaba_key, base_url=alibaba_base)
            return adapter, model_name

        # 3. DeepSeek Native
        if provider_key == "deepseek":
            deepseek_base = os.getenv(
                "DEEPSEEK_BASE_URL", getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            ).rstrip("/")
            deepseek_key = os.getenv("DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", ""))
            if not deepseek_key and not self.force_mock:
                raise ValueError(
                    f"Chưa cấu hình DEEPSEEK_API_KEY cho model '{model_name}'. "
                    "Vui lòng thiết lập biến môi trường DEEPSEEK_API_KEY trên Railway Variables."
                )
            adapter = OpenAIAdapter(api_key=deepseek_key, base_url=deepseek_base)
            adapter.provider_name = "deepseek"
            return adapter, model_name

        # 4. DeepInfra
        if provider_key == "deepinfra":
            deepinfra_base = os.getenv(
                "DEEPINFRA_BASE_URL",
                getattr(settings, "DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai"),
            ).rstrip("/")
            deepinfra_key = os.getenv("DEEPINFRA_API_KEY", getattr(settings, "DEEPINFRA_API_KEY", ""))
            if not deepinfra_key and not self.force_mock:
                raise ValueError(
                    f"Chưa cấu hình DEEPINFRA_API_KEY cho model '{model_name}'. "
                    "Vui lòng thiết lập biến môi trường DEEPINFRA_API_KEY trên Railway Variables."
                )
            adapter = DeepInfraAdapter(api_key=deepinfra_key, base_url=deepinfra_base)
            return adapter, model_name

        adapter = self.adapters.get(provider_key)
        if not adapter:
            logger.error(
                "MultiProviderRouter: Provider '%s' from spec '%s' is not supported. Supported: %s",
                provider_key,
                role_model_spec,
                list(self.adapters.keys()),
            )
            raise ValueError(
                f"Provider '{provider_key}' không được hỗ trợ. Hệ thống sử dụng 4 nhà cung cấp độc lập: gemini, alibaba, deepseek, deepinfra (và mock)."
            )
        return adapter, model_name

    async def call_for_role(
        self,
        *,
        role_model_spec: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        timeout_sec: float = 90.0,
    ) -> tuple[T, LLMCallResult]:
        adapter, model_name = self.resolve_spec(role_model_spec)
        try:
            return await adapter.generate_structured(
                model_name=model_name,
                prompt_version=prompt_version,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=response_schema,
                timeout_sec=timeout_sec,
            )
        except Exception as e:
            logger.error(
                "MultiProviderRouter: LLM call FAILED for role_model_spec='%s' (model='%s', provider='%s'): %s",
                role_model_spec,
                model_name,
                getattr(adapter, "provider_name", "unknown"),
                e,
                exc_info=True,
            )
            raise

    async def retrieve_source_with_grounding(
        self,
        *,
        role_model_spec: str,
        system_prompt: str,
        user_prompt: str,
        timeout_sec: float = 12.0,
    ) -> tuple[dict[str, Any], LLMCallResult]:
        adapter, model_name = self.resolve_spec(role_model_spec)
        if hasattr(adapter, "generate_with_grounding"):
            return await adapter.generate_with_grounding(
                model_name=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_sec=timeout_sec,
            )
        raise NotImplementedError(
            f"Provider '{getattr(adapter, 'provider_name', type(adapter).__name__)}' không hỗ trợ tra cứu Google Search Grounding."
        )


def get_available_models_catalog() -> list[dict[str, Any]]:
    import os
    gemini_avail = bool(settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY"))
    deepseek_avail = bool(
        os.getenv("DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", ""))
    )
    alibaba_avail = bool(
        os.getenv("ALIBABA_API_KEY", getattr(settings, "ALIBABA_API_KEY", ""))
    )
    deepinfra_avail = bool(
        os.getenv("DEEPINFRA_API_KEY", getattr(settings, "DEEPINFRA_API_KEY", ""))
    )

    return [
        {
            "id": "alibaba:qwen2.5-math-72b-instruct",
            "provider": "alibaba",
            "model_name": "qwen2.5-math-72b-instruct",
            "configured": alibaba_avail,
            "recommended_roles": ["solver_a", "solver_b", "solver_c", "judge"],
        },
        {
            "id": "alibaba:qwen-plus",
            "provider": "alibaba",
            "model_name": "qwen-plus",
            "configured": alibaba_avail,
            "recommended_roles": ["solver_a", "solver_b", "solver_c", "judge"],
        },
        {
            "id": "alibaba:qwen-max",
            "provider": "alibaba",
            "model_name": "qwen-max",
            "configured": alibaba_avail,
            "recommended_roles": ["solver_a", "solver_b", "skeptic", "judge"],
        },
        {
            "id": "deepseek:deepseek-reasoner",
            "provider": "deepseek",
            "model_name": "deepseek-reasoner",
            "configured": deepseek_avail,
            "recommended_roles": ["solver_a", "solver_b", "solver_c", "skeptic"],
        },
        {
            "id": "deepseek:deepseek-chat",
            "provider": "deepseek",
            "model_name": "deepseek-chat",
            "configured": deepseek_avail,
            "recommended_roles": ["solver_b", "solver_c"],
        },
        {
            "id": "deepinfra:meta-llama/Llama-3.3-70B-Instruct",
            "provider": "deepinfra",
            "model_name": "meta-llama/Llama-3.3-70B-Instruct",
            "configured": deepinfra_avail,
            "recommended_roles": ["skeptic", "judge"],
        },
        {
            "id": "deepinfra:Qwen/Qwen2.5-72B-Instruct",
            "provider": "deepinfra",
            "model_name": "Qwen/Qwen2.5-72B-Instruct",
            "configured": deepinfra_avail,
            "recommended_roles": ["solver_a", "solver_b", "solver_c", "judge"],
        },
        {
            "id": "deepinfra:deepseek-ai/DeepSeek-R1",
            "provider": "deepinfra",
            "model_name": "deepseek-ai/DeepSeek-R1",
            "configured": deepinfra_avail,
            "recommended_roles": ["solver_a", "solver_b", "solver_c", "skeptic"],
        },
        {
            "id": "deepinfra:deepseek-ai/DeepSeek-V3",
            "provider": "deepinfra",
            "model_name": "deepseek-ai/DeepSeek-V3",
            "configured": deepinfra_avail,
            "recommended_roles": ["solver_a", "solver_b", "solver_c"],
        },
        {
            "id": "gemini:gemini-2.5-flash",
            "provider": "gemini",
            "model_name": "gemini-2.5-flash",
            "configured": gemini_avail,
            "recommended_roles": ["normalizer", "source_finder"],
        },
        {
            "id": "gemini:gemini-2.5-pro",
            "provider": "gemini",
            "model_name": "gemini-2.5-pro",
            "configured": gemini_avail,
            "recommended_roles": ["solver_a", "solver_b", "judge"],
        },
        {
            "id": "mock:deterministic-olympiad-v1",
            "provider": "mock",
            "model_name": "deterministic-olympiad-v1",
            "configured": True,
            "recommended_roles": ["normalizer", "source_finder", "solver_a", "solver_b", "skeptic", "judge"],
        },
    ]
