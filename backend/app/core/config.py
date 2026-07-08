"""
Backend configuration — reads from environment variables.
On Render: set env vars in Dashboard → Environment.
Locally: create .env file from .env.example.
"""
import json
import os
import secrets
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    PORT: int = int(os.environ.get("PORT", 8000))
    HOST: str = "0.0.0.0"
    DEBUG: bool = False

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_chat.db"

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.DATABASE_URL.lower()

    @property
    def sync_database_url(self) -> str:
        """Alembic needs sync driver."""
        url = self.DATABASE_URL
        if url.startswith("sqlite+aiosqlite"):
            return url.replace("sqlite+aiosqlite", "sqlite")
        if url.startswith("postgresql+asyncpg"):
            return url.replace("+asyncpg", "")
        if url.startswith("postgresql+psycopg"):
            return url.replace("+psycopg", "+psycopg2")
        return url

    # Firebase
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""

    @property
    def firebase_credentials_dict(self) -> Optional[dict]:
        if not self.FIREBASE_SERVICE_ACCOUNT_JSON:
            return None
        try:
            return json.loads(self.FIREBASE_SERVICE_ACCOUNT_JSON)
        except json.JSONDecodeError:
            return None

    # LLM
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEFAULT_LLM_PROVIDER: str = "groq"
    DEFAULT_MODEL: str = "llama-3.3-70b-versatile"

    # Search
    TAVILY_API_KEY: str = ""
    TAVILY_BASE_URL: str = "https://api.tavily.com"

    # Agent
    MAX_AGENT_ITERATIONS: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
