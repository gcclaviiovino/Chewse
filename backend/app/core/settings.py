from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

_ENV_LOADED = False


def load_env_file() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        _ENV_LOADED = True
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

    _ENV_LOADED = True


class Settings(BaseModel):
    app_name: str = Field(default_factory=lambda: os.getenv("APP_NAME", "Social Food AI Pipeline"))
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    backend_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    chroma_path: Path = Field(default_factory=lambda: Path(os.getenv("CHROMA_PATH", Path(__file__).resolve().parents[2] / "chroma")))
    off_data_dir: Path = Field(default_factory=lambda: Path(os.getenv("OFF_DATA_DIR", Path(__file__).resolve().parents[2] / "data" / "off_subset")))

    llm_base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.regolo.ai"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen3-vl-32b"))
    embedding_base_url: str = Field(default_factory=lambda: os.getenv("EMBEDDING_BASE_URL", "https://api.regolo.ai"))
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "Qwen3-Embedding-8B"))
    regolo_api_key: str = Field(default_factory=lambda: os.getenv("REGOLO_API_KEY", ""))
    regolo_api_header: str = Field(default_factory=lambda: os.getenv("REGOLO_API_HEADER", "Authorization"))
    regolo_api_prefix: str = Field(default_factory=lambda: os.getenv("REGOLO_API_PREFIX", "Bearer"))
    openfoodfacts_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENFOODFACTS_BASE_URL", "https://world.openfoodfacts.org/api/v2")
    )
    request_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")))
    rag_top_k: int = Field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "3")))

    def build_auth_headers(self) -> dict:
        if not self.regolo_api_key:
            return {}
        if self.regolo_api_prefix:
            return {self.regolo_api_header: "{} {}".format(self.regolo_api_prefix, self.regolo_api_key)}
        return {self.regolo_api_header: self.regolo_api_key}

    @staticmethod
    def normalize_base_url(base_url: str) -> str:
        return base_url.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_env_file()
    return Settings()
