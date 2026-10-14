from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Math Council API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://mathcouncil:mathcouncil_dev_secret@db:5432/mathcouncil_db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None) -> str:
        if not v:
            return "postgresql+asyncpg://mathcouncil:mathcouncil_dev_secret@db:5432/mathcouncil_db"
        # Convert postgres:// or postgresql:// to postgresql+asyncpg:// if async driver not specified
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    REDIS_URL: str = "redis://redis:6379/0"
    ENVIRONMENT: str = "development"

    # Chế độ mặc định ("mock" để chạy test miễn phí, "live" để gọi AI thật)
    DEFAULT_LLM_PROVIDER: str = "mock"

    # API Keys cho từng Provider
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_COMPATIBLE_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENAI_COMPATIBLE_API_KEY: str = ""

    @field_validator("OPENAI_COMPATIBLE_API_KEY", mode="before")
    @classmethod
    def assemble_openai_compatible_key(cls, v: str | None) -> str:
        import os
        if v:
            return v
        return os.getenv("OPENROUTER_API_KEY", "") or ""

    @field_validator("OPENAI_COMPATIBLE_BASE_URL", mode="before")
    @classmethod
    def assemble_openai_compatible_base_url(cls, v: str | None) -> str:
        import os
        key = os.getenv("OPENAI_COMPATIBLE_API_KEY", "") or os.getenv("OPENROUTER_API_KEY", "")
        if key.startswith("sk-or-") or os.getenv("OPENROUTER_API_KEY"):
            return "https://openrouter.ai/api/v1"
        return v or "https://openrouter.ai/api/v1"

    # DeepSeek API Provider
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_API_KEY: str = ""

    # Alibaba Cloud Model Studio (MaaS) API Provider
    ALIBABA_BASE_URL: str = "https://ws-dgcpkbso457jl8mu.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    ALIBABA_API_KEY: str = ""

    # DeepInfra API Provider
    DEEPINFRA_BASE_URL: str = "https://api.deepinfra.com/v1/openai"
    DEEPINFRA_API_KEY: str = ""

    # Cấu hình Model mặc định cho từng vai trò trong Hội đồng (provider:model_name)
    ROLE_NORMALIZER_MODEL: str = "gemini:gemini-2.5-flash"
    ROLE_SOURCE_FINDER_MODEL: str = "openai_compatible:google/gemini-2.5-flash:online"
    ROLE_SOLVER_A_MODEL: str = "gemini:gemini-2.5-pro"
    ROLE_SOLVER_B_MODEL: str = "openai:gpt-4o"

    @field_validator("ROLE_SOLVER_B_MODEL", mode="before")
    @classmethod
    def assemble_solver_b_model(cls, v: str | None) -> str:
        import os
        env_val = os.getenv("ROLE_SOLVER_B_MODEL")
        if env_val:
            return env_val
        if v and v != "openai:gpt-4o":
            return v
        # Mặc định đọc từ deepseek:deepseek-reasoner nếu DEEPSEEK_API_KEY được cấu hình
        if os.getenv("DEEPSEEK_API_KEY"):
            return "deepseek:deepseek-reasoner"
        return v or "openai:gpt-4o"

    ROLE_SOLVER_C_MODEL: str = "openai_compatible:openai/o3-mini"
    ROLE_SKEPTIC_MODEL: str = "anthropic:claude-3-7-sonnet-latest"
    ROLE_JUDGE_MODEL: str = "openai:gpt-4o"

    # Bật/tắt tính năng tìm nguồn gốc đề toán
    ENABLE_SOURCE_DISCOVERY: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
