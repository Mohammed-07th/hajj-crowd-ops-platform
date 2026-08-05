"""Central configuration, read from .env via pydantic-settings.

Everything the pipeline needs to locate infrastructure or tune behaviour lives
here so no module hardcodes a host, path or model name.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- OpenRouter --------------------------------------------------------
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model_primary: str = "meta-llama/llama-3.3-70b-instruct:free"
    llm_model_fallbacks: str = ""
    openrouter_site_url: str = ""
    openrouter_app_name: str = "hajj-crowd-ops-platform"
    llm_max_retries: int = 5
    llm_timeout_seconds: int = 120

    # --- local models ------------------------------------------------------
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- infrastructure ----------------------------------------------------
    kafka_bootstrap_servers: str = "localhost:9092"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "hajj_sop_v1"
    delta_root: str = "./delta"
    openlineage_namespace: str = "hajj-ops"
    openlineage_events_path: str = "./docs/evidence/lineage/events.jsonl"
    pii_salt: str = "change-me-in-production"

    # --- retrieval ---------------------------------------------------------
    rrf_k: int = 60
    retrieve_top_k: int = 50
    rerank_top_k: int = 5

    @property
    def fallback_models(self) -> list[str]:
        return [m.strip() for m in self.llm_model_fallbacks.split(",") if m.strip()]

    def delta_path(self, table: str) -> str:
        """Absolute path to a Delta table, so behaviour does not depend on cwd.

        Airflow runs tasks from its own working directory; a relative DELTA_ROOT
        would silently create a second set of tables under AIRFLOW_HOME.
        """
        root = Path(self.delta_root)
        if not root.is_absolute():
            root = REPO_ROOT / root
        return str(root / table)

    @property
    def reference_dir(self) -> Path:
        return REPO_ROOT / "data" / "reference"


settings = Settings()
