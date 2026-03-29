from __future__ import annotations

import os
from json import loads as json_loads
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
    default_locale: str = Field(default_factory=lambda: os.getenv("DEFAULT_LOCALE", "it-IT"))

    backend_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    chroma_path: Path = Field(default_factory=lambda: Path(os.getenv("CHROMA_PATH", Path(__file__).resolve().parents[2] / "chroma")))
    off_data_dir: Path = Field(default_factory=lambda: Path(os.getenv("OFF_DATA_DIR", Path(__file__).resolve().parents[2] / "data" / "off_subset")))
    allowed_image_roots_raw: str = Field(default_factory=lambda: os.getenv("ALLOWED_IMAGE_ROOTS", ""))

    llm_base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.regolo.ai"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen3-vl-32b"))
    llm_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))))
    llm_retry_count: int = Field(default_factory=lambda: int(os.getenv("LLM_RETRY_COUNT", "2")))
    embedding_base_url: str = Field(default_factory=lambda: os.getenv("EMBEDDING_BASE_URL", "https://api.regolo.ai"))
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "Qwen3-Embedding-8B"))
    embedding_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))))
    embedding_retry_count: int = Field(default_factory=lambda: int(os.getenv("EMBEDDING_RETRY_COUNT", "2")))
    regolo_api_key: str = Field(default_factory=lambda: os.getenv("REGOLO_API_KEY", ""))
    regolo_api_header: str = Field(default_factory=lambda: os.getenv("REGOLO_API_HEADER", "Authorization"))
    regolo_api_prefix: str = Field(default_factory=lambda: os.getenv("REGOLO_API_PREFIX", "Bearer"))
    off_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "OFF_BASE_URL",
            os.getenv("OPENFOODFACTS_BASE_URL", "https://world.openfoodfacts.org/api/v2"),
        )
    )
    openfoodfacts_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "OFF_BASE_URL",
            os.getenv("OPENFOODFACTS_BASE_URL", "https://world.openfoodfacts.org/api/v2"),
        )
    )
    off_user_agent: str = Field(
        default_factory=lambda: os.getenv("OFF_USER_AGENT", "SocialFoodBackend/1.0 (support@example.com)")
    )
    off_username: str = Field(default_factory=lambda: os.getenv("OFF_USERNAME", ""))
    off_password: str = Field(default_factory=lambda: os.getenv("OFF_PASSWORD", ""))
    off_timeout_connect_seconds: float = Field(
        default_factory=lambda: float(
            os.getenv(
                "OFF_TIMEOUT_CONNECT_SECONDS",
                os.getenv("OFF_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
            )
        )
    )
    off_timeout_read_seconds: float = Field(
        default_factory=lambda: float(
            os.getenv(
                "OFF_TIMEOUT_READ_SECONDS",
                os.getenv("OFF_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
            )
        )
    )
    off_timeout_seconds: float = Field(
        default_factory=lambda: float(
            os.getenv("OFF_TIMEOUT_READ_SECONDS", os.getenv("OFF_TIMEOUT_SECONDS", os.getenv("REQUEST_TIMEOUT_SECONDS", "30")))
        )
    )
    off_max_retries: int = Field(
        default_factory=lambda: int(os.getenv("OFF_MAX_RETRIES", os.getenv("OFF_RETRY_COUNT", "2")))
    )
    off_retry_count: int = Field(
        default_factory=lambda: int(os.getenv("OFF_MAX_RETRIES", os.getenv("OFF_RETRY_COUNT", "2")))
    )
    off_backoff_base_ms: int = Field(
        default_factory=lambda: int(
            os.getenv("OFF_BACKOFF_BASE_MS", str(int(float(os.getenv("RETRY_BACKOFF_BASE_SECONDS", "0.25")) * 1000)))
        )
    )
    off_respect_retry_after: bool = Field(
        default_factory=lambda: os.getenv("OFF_RESPECT_RETRY_AFTER", "true").lower() == "true"
    )
    off_cache_enabled: bool = Field(default_factory=lambda: os.getenv("OFF_CACHE_ENABLED", "true").lower() == "true")
    off_cache_ttl_seconds: int = Field(default_factory=lambda: int(os.getenv("OFF_CACHE_TTL_SECONDS", "3600")))
    off_cache_not_found_ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("OFF_CACHE_NOT_FOUND_TTL_SECONDS", "300"))
    )
    request_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")))
    retry_backoff_base_seconds: float = Field(default_factory=lambda: float(os.getenv("RETRY_BACKOFF_BASE_SECONDS", "0.25")))
    retry_jitter_seconds: float = Field(default_factory=lambda: float(os.getenv("RETRY_JITTER_SECONDS", "0.1")))
    rag_top_k: int = Field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "3")))
    rag_score_threshold: float = Field(default_factory=lambda: float(os.getenv("RAG_SCORE_THRESHOLD", "0.35")))
    rag_metadata_filters_raw: str = Field(default_factory=lambda: os.getenv("RAG_METADATA_FILTERS", ""))
    similar_products_candidate_limit: int = Field(
        default_factory=lambda: int(os.getenv("SIMILAR_PRODUCTS_CANDIDATE_LIMIT", "20"))
    )
    similar_products_shortlist_size: int = Field(
        default_factory=lambda: int(os.getenv("SIMILAR_PRODUCTS_SHORTLIST_SIZE", "5"))
    )
    similar_products_similarity_threshold: float = Field(
        default_factory=lambda: float(os.getenv("SIMILAR_PRODUCTS_SIMILARITY_THRESHOLD", "0.35"))
    )
    llm_input_max_chars: int = Field(default_factory=lambda: int(os.getenv("LLM_INPUT_MAX_CHARS", "4000")))
    llm_output_max_chars: int = Field(default_factory=lambda: int(os.getenv("LLM_OUTPUT_MAX_CHARS", "12000")))
    explanation_short_max_chars: int = Field(default_factory=lambda: int(os.getenv("EXPLANATION_SHORT_MAX_CHARS", "320")))
    explanation_bullet_max_chars: int = Field(default_factory=lambda: int(os.getenv("EXPLANATION_BULLET_MAX_CHARS", "220")))
    max_request_bytes: int = Field(default_factory=lambda: int(os.getenv("MAX_REQUEST_BYTES", "1048576")))
    enable_pipeline_debug_last: bool = Field(default_factory=lambda: os.getenv("ENABLE_PIPELINE_DEBUG_LAST", "").lower() == "true")

    def build_auth_headers(self) -> dict:
        if not self.regolo_api_key:
            return {}
        if self.regolo_api_prefix:
            return {self.regolo_api_header: "{} {}".format(self.regolo_api_prefix, self.regolo_api_key)}
        return {self.regolo_api_header: self.regolo_api_key}

    @staticmethod
    def normalize_base_url(base_url: str) -> str:
        return base_url.rstrip("/")

    def allowed_image_roots(self) -> list[Path]:
        roots = [item.strip() for item in self.allowed_image_roots_raw.split(",") if item.strip()]
        if not roots:
            roots = [str(self.backend_dir)]
        return [Path(item).expanduser().resolve() for item in roots]

    def rag_metadata_filters(self) -> dict:
        raw = self.rag_metadata_filters_raw.strip()
        if not raw:
            return {}
        try:
            parsed = json_loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_env_file()
    return Settings()
