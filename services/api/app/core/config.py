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
    OPENAI_COMPATIBLE_BASE_URL: str = "https://api.deepseek.com/v1"
    OPENAI_COMPATIBLE_API_KEY: str = ""

    # Cấu hình Model mặc định cho từng vai trò trong Hội đồng (provider:model_name)
    ROLE_NORMALIZER_MODEL: str = "gemini:gemini-2.5-flash"
    ROLE_SOURCE_FINDER_MODEL: str = "openai_compatible:google/gemini-2.5-flash:online"
    ROLE_SOLVER_A_MODEL: str = "gemini:gemini-2.5-pro"
    ROLE_SOLVER_B_MODEL: str = "openai:gpt-4o"
    ROLE_SOLVER_C_MODEL: str = "openai_compatible:deepseek-reasoner"
    ROLE_SKEPTIC_MODEL: str = "anthropic:claude-3-7-sonnet-latest"
    ROLE_JUDGE_MODEL: str = "openai:gpt-4o"

    # Bật/tắt tính năng tìm nguồn gốc đề toán
    ENABLE_SOURCE_DISCOVERY: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
