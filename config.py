"""Small environment-based configuration for the offline scaffold."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import math
import json
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
    workflow_db_path: Path | None = None
    action_backend: str = "simulation"
    connector_base_url: str = "http://127.0.0.1:9000"
    connector_api_key: str | None = field(default=None, repr=False)
    connector_timeout: float = 30.0
    connector_receipt_db_path: Path | None = None
    llm_provider: str = "none"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3.5:9b"
    llm_timeout: float = 120.0
    llm_context: int = 8192
    llm_max_tokens: int = 1200
    api_cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    api_upload_max_bytes: int = 5 * 1024 * 1024
    approval_credentials: tuple[tuple[str, str], ...] = field(default=(), repr=False)

    def __post_init__(self):
        if self.memory_backend not in {"mock", "sqlite", "hindsight"}:
            raise ValueError("MEMORY_BACKEND must be mock, sqlite, or hindsight")
        if self.action_backend not in {"simulation", "connector"}:
            raise ValueError("ACTION_BACKEND must be simulation or connector")
        url = urlparse(self.hindsight_base_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("HINDSIGHT_BASE_URL must be an HTTP(S) URL without credentials/query/fragment")
        if not self.hindsight_bank_id.strip():
            raise ValueError("HINDSIGHT_BANK_ID must not be empty")
        if not math.isfinite(self.hindsight_timeout) or self.hindsight_timeout <= 0:
            raise ValueError("HINDSIGHT_TIMEOUT must be finite and positive")
        connector = urlparse(self.connector_base_url)
        if (connector.scheme not in {"http", "https"} or not connector.hostname
                or connector.username or connector.password or connector.query or connector.fragment):
            raise ValueError("CONNECTOR_BASE_URL must be an HTTP(S) URL without credentials/query/fragment")
        if not math.isfinite(self.connector_timeout) or self.connector_timeout <= 0:
            raise ValueError("CONNECTOR_TIMEOUT must be finite and positive")
        if self.llm_provider not in {"none", "ollama"}:
            raise ValueError("LLM_PROVIDER must be none or ollama")
        endpoint = urlparse(self.llm_base_url)
        if endpoint.scheme not in {"http", "https"} or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError("LLM_BASE_URL must be an HTTP(S) URL without credentials/query/fragment")
        if not self.llm_model.strip() or not math.isfinite(self.llm_timeout) or self.llm_timeout <= 0:
            raise ValueError("LLM_MODEL and a positive finite LLM_TIMEOUT are required")
        if not 2048 <= self.llm_context <= 32768 or not 128 <= self.llm_max_tokens <= 4096:
            raise ValueError("LLM_CONTEXT must be 2048..32768; LLM_MAX_TOKENS must be 128..4096")
        for origin in self.api_cors_origins:
            parsed = urlparse(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path not in {"", "/"}):
                raise ValueError("API_CORS_ORIGINS must contain HTTP(S) origins without paths")
        if not 1024 <= self.api_upload_max_bytes <= 25 * 1024 * 1024:
            raise ValueError("API_UPLOAD_MAX_BYTES must be between 1 KiB and 25 MiB")
        reviewers = [reviewer for reviewer, _ in self.approval_credentials]
        tokens = [token for _, token in self.approval_credentials]
        if (any(not reviewer.strip() or not token for reviewer, token in self.approval_credentials)
                or len(reviewers) != len(set(reviewers)) or len(tokens) != len(set(tokens))):
            raise ValueError("APPROVAL_IDENTITIES_JSON requires unique, non-empty reviewers and tokens")

    @classmethod
    def from_env(cls, env_file: Path | None = None):
        root = Path(__file__).resolve().parent
        values = {**dotenv_values(env_file or root / ".env", interpolate=False), **os.environ}
        def value(key, default):
            return values.get(key) if values.get(key) is not None else default
        def path(key, default):
            candidate = Path(value(key, str(default)))
            return (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        origins = tuple(item.strip() for item in value(
            "API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if item.strip())
        try:
            approval_map = json.loads(value("APPROVAL_IDENTITIES_JSON", "{}"))
            if not isinstance(approval_map, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                              for k, v in approval_map.items()):
                raise ValueError
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("APPROVAL_IDENTITIES_JSON must be a JSON object of reviewer-to-token strings") from exc
        return cls(data_dir=path("INCIDENT_DATA_DIR", root / "data"),
                   memory_backend=value("MEMORY_BACKEND", "mock"),
                   hindsight_base_url=value("HINDSIGHT_BASE_URL", "http://localhost:8888").rstrip("/"),
                   hindsight_bank_id=value("HINDSIGHT_BANK_ID", "adaptive-incident-intelligence"),
                   hindsight_api_key=value("HINDSIGHT_API_KEY", "") or None,
                   hindsight_timeout=float(value("HINDSIGHT_TIMEOUT", "120")),
                   sqlite_path=path("SQLITE_PATH", root / ".runtime" / "incidents.sqlite3"),
                   workflow_db_path=path("WORKFLOW_DB_PATH", root / ".runtime" / "workflows.sqlite3"),
                   action_backend=value("ACTION_BACKEND", "simulation"),
                   connector_base_url=value("CONNECTOR_BASE_URL", "http://127.0.0.1:9000").rstrip("/"),
                   connector_api_key=value("CONNECTOR_API_KEY", "") or None,
                   connector_timeout=float(value("CONNECTOR_TIMEOUT", "30")),
                   connector_receipt_db_path=path("CONNECTOR_RECEIPT_DB_PATH", root / ".runtime" / "connector-receipts.sqlite3"),
                   llm_provider=value("LLM_PROVIDER", "none"),
                   llm_base_url=value("LLM_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
                   llm_model=value("LLM_MODEL", "qwen3.5:9b"),
                   llm_timeout=float(value("LLM_TIMEOUT", "120")),
                   llm_context=int(value("LLM_CONTEXT", "8192")),
                   llm_max_tokens=int(value("LLM_MAX_TOKENS", "1200")),
                   api_cors_origins=origins,
                   api_upload_max_bytes=int(value("API_UPLOAD_MAX_BYTES", str(5 * 1024 * 1024))),
                   approval_credentials=tuple(approval_map.items()))
