from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Shipment Delay Risk Assessment Platform")
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    model_dir: Path = Path(os.getenv("MODEL_DIR", "models"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    straive_base_url: str = os.getenv("STRAIVE_GEMINI_BASE_URL", "")
    straive_api_key: str = os.getenv("STRAIVE_GEMINI_API_KEY", "")
    straive_model: str = os.getenv("STRAIVE_GEMINI_MODEL", "gemini-2.5-pro")
    straive_timeout_seconds: int = int(os.getenv("STRAIVE_GEMINI_TIMEOUT_SECONDS", "20"))
    straive_max_retries: int = int(os.getenv("STRAIVE_GEMINI_MAX_RETRIES", "2"))
    use_mock_llm: bool = os.getenv("USE_MOCK_LLM", "true").lower() == "true"

    @property
    def shipments_path(self) -> Path:
        return self.data_dir / "synthetic_shipments.csv"

    @property
    def scored_shipments_path(self) -> Path:
        return self.data_dir / "scored_shipments.csv"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.model_dir.mkdir(parents=True, exist_ok=True)
