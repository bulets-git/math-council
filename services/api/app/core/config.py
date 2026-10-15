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

    # API Keys & Base URLs cho từng Provider
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Các nhà cung cấp API:
    # 1. Google Gemini
    # 2. DeepSeek Native
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_API_KEY: str = ""

    # 3. Alibaba Cloud Model Studio (MaaS)
    ALIBABA_BASE_URL: str = "https://ws-dgcpkbso457jl8mu.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    ALIBABA_API_KEY: str = ""

    # 4. DeepInfra
    DEEPINFRA_BASE_URL: str = "https://api.deepinfra.com/v1/openai"
    DEEPINFRA_API_KEY: str = ""

    # 5. OpenRouter
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_KEY: str = ""

    # Cấu hình Model mặc định cho từng vai trò trong Hội đồng (provider:model_name)
    # Mặc định sử dụng Gemini và DeepSeek theo quy chuẩn
    ROLE_NORMALIZER_MODEL: str = "gemini:gemini-2.5-flash"
    ROLE_RETRIEVER_MODEL: str = "gemini:gemini-2.5-flash"
    ROLE_SOURCE_FINDER_MODEL: str = "gemini:gemini-2.5-flash"

    @field_validator("ROLE_RETRIEVER_MODEL", mode="before")
    @classmethod
    def assemble_retriever_model(cls, v: str | None) -> str:
        import os
        env_val = os.getenv("ROLE_RETRIEVER_MODEL") or os.getenv("ROLE_SOURCE_FINDER_MODEL")
        if env_val:
            return env_val
        return v or "gemini:gemini-2.5-flash"

    @field_validator("ROLE_SOURCE_FINDER_MODEL", mode="before")
    @classmethod
    def assemble_source_finder_model(cls, v: str | None) -> str:
        import os
        env_val = os.getenv("ROLE_RETRIEVER_MODEL") or os.getenv("ROLE_SOURCE_FINDER_MODEL")
        if env_val:
            return env_val
        return v or "gemini:gemini-2.5-flash"

    ROLE_SOLVER_A_MODEL: str = "deepseek:deepseek-chat"
    ROLE_SOLVER_B_MODEL: str = "deepseek:deepseek-reasoner"

    @field_validator("ROLE_SOLVER_A_MODEL", mode="before")
    @classmethod
    def assemble_solver_a_model(cls, v: str | None) -> str:
        import os
        env_val = os.getenv("ROLE_SOLVER_A_MODEL")
        if env_val:
            return env_val
        return v or "deepseek:deepseek-chat"

    @field_validator("ROLE_SOLVER_B_MODEL", mode="before")
    @classmethod
    def assemble_solver_b_model(cls, v: str | None) -> str:
        import os
        env_val = os.getenv("ROLE_SOLVER_B_MODEL")
        if env_val:
            return env_val
        return v or "deepseek:deepseek-reasoner"

    ROLE_SOLVER_C_MODEL: str = "gemini:gemini-2.5-flash"
    ROLE_SKEPTIC_MODEL: str = "gemini:gemini-2.5-pro"
    ROLE_JUDGE_MODEL: str = "gemini:gemini-2.5-pro"

    # Bật/tắt tính năng tìm nguồn gốc đề toán
    ENABLE_SOURCE_DISCOVERY: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
