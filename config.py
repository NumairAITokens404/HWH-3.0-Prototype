"""Small environment-based configuration for the offline scaffold."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import math
from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    memory_backend: str = "mock"
    hindsight_base_url: str = "http://localhost:8888"
    hindsight_bank_id: str = "adaptive-incident-intelligence"
    hindsight_api_key: str | None = field(default=None, repr=False)
    hindsight_timeout: float = 120.0
    sqlite_path: Path = field(default_factory=lambda: Path(__file__).resolve().parent / ".runtime" / "incidents.sqlite3")
    llm_provider: str = "none"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3.5:9b"
    llm_timeout: float = 120.0
    llm_context: int = 8192
    llm_max_tokens: int = 1200

    def __post_init__(self):
        if self.memory_backend not in {"mock", "sqlite", "hindsight"}:
            raise ValueError("MEMORY_BACKEND must be mock, sqlite, or hindsight")
        url = urlparse(self.hindsight_base_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("HINDSIGHT_BASE_URL must be an HTTP(S) URL without credentials/query/fragment")
        if not self.hindsight_bank_id.strip():
            raise ValueError("HINDSIGHT_BANK_ID must not be empty")
        if not math.isfinite(self.hindsight_timeout) or self.hindsight_timeout <= 0:
            raise ValueError("HINDSIGHT_TIMEOUT must be finite and positive")
        if self.llm_provider not in {"none", "ollama"}:
            raise ValueError("LLM_PROVIDER must be none or ollama")
        endpoint = urlparse(self.llm_base_url)
        if endpoint.scheme not in {"http", "https"} or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError("LLM_BASE_URL must be an HTTP(S) URL without credentials/query/fragment")
        if not self.llm_model.strip() or not math.isfinite(self.llm_timeout) or self.llm_timeout <= 0:
            raise ValueError("LLM_MODEL and a positive finite LLM_TIMEOUT are required")
        if not 2048 <= self.llm_context <= 32768 or not 128 <= self.llm_max_tokens <= 4096:
            raise ValueError("LLM_CONTEXT must be 2048..32768; LLM_MAX_TOKENS must be 128..4096")

    @classmethod
    def from_env(cls, env_file: Path | None = None):
        root = Path(__file__).resolve().parent
        values = {**dotenv_values(env_file or root / ".env", interpolate=False), **os.environ}
        def value(key, default):
            return values.get(key) if values.get(key) is not None else default
        def path(key, default):
            candidate = Path(value(key, str(default)))
            return (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        return cls(data_dir=path("INCIDENT_DATA_DIR", root / "data"),
                   memory_backend=value("MEMORY_BACKEND", "mock"),
                   hindsight_base_url=value("HINDSIGHT_BASE_URL", "http://localhost:8888").rstrip("/"),
                   hindsight_bank_id=value("HINDSIGHT_BANK_ID", "adaptive-incident-intelligence"),
                   hindsight_api_key=value("HINDSIGHT_API_KEY", "") or None,
                   hindsight_timeout=float(value("HINDSIGHT_TIMEOUT", "120")),
                   sqlite_path=path("SQLITE_PATH", root / ".runtime" / "incidents.sqlite3"),
                   llm_provider=value("LLM_PROVIDER", "none"),
                   llm_base_url=value("LLM_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
                   llm_model=value("LLM_MODEL", "qwen3.5:9b"),
                   llm_timeout=float(value("LLM_TIMEOUT", "120")),
                   llm_context=int(value("LLM_CONTEXT", "8192")),
                   llm_max_tokens=int(value("LLM_MAX_TOKENS", "1200")))
