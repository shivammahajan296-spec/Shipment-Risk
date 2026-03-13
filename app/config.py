from __future__ import annotations

import json
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
    straive_base_url: str = os.getenv(
        "STRAIVE_GEMINI_BASE_URL",
        "https://llmfoundry.straive.com/gemini/v1beta/openai/chat/completions",
    )
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

    @property
    def runtime_settings_path(self) -> Path:
        return self.data_dir / "runtime_settings.json"

    def load_runtime_overrides(self) -> None:
        if not self.runtime_settings_path.exists():
            return
        try:
            payload = json.loads(self.runtime_settings_path.read_text())
        except Exception:
            return

        self.straive_api_key = payload.get("straive_api_key", self.straive_api_key)
        self.straive_model = payload.get("straive_model", self.straive_model)
        self.use_mock_llm = payload.get("use_mock_llm", self.use_mock_llm)

    def save_runtime_overrides(
        self,
        *,
        straive_api_key: str,
        straive_model: str | None = None,
        use_mock_llm: bool = False,
    ) -> None:
        payload = {
            "straive_api_key": straive_api_key.strip(),
            "straive_model": (straive_model or self.straive_model).strip(),
            "use_mock_llm": use_mock_llm,
        }
        self.runtime_settings_path.write_text(json.dumps(payload, indent=2))
        self.straive_api_key = payload["straive_api_key"]
        self.straive_model = payload["straive_model"]
        self.use_mock_llm = payload["use_mock_llm"]

    def clear_runtime_overrides(self) -> None:
        if self.runtime_settings_path.exists():
            self.runtime_settings_path.unlink()
        self.straive_base_url = os.getenv("STRAIVE_GEMINI_BASE_URL", "")
        self.straive_api_key = os.getenv("STRAIVE_GEMINI_API_KEY", "")
        self.straive_model = os.getenv("STRAIVE_GEMINI_MODEL", "gemini-2.5-pro")
        self.use_mock_llm = os.getenv("USE_MOCK_LLM", "true").lower() == "true"

    def llm_settings_view(self) -> dict[str, str | bool]:
        masked_key = ""
        if self.straive_api_key:
            masked_key = f"{self.straive_api_key[:4]}...{self.straive_api_key[-4:]}" if len(self.straive_api_key) > 8 else "Configured"
        return {
            "straive_base_url": self.straive_base_url,
            "straive_api_key_masked": masked_key,
            "straive_model": self.straive_model,
            "use_mock_llm": self.use_mock_llm,
            "configured": bool(self.straive_base_url and self.straive_api_key),
        }


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.model_dir.mkdir(parents=True, exist_ok=True)
settings.load_runtime_overrides()
