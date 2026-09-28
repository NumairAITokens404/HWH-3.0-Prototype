"""Small environment-based configuration for the offline scaffold."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import math


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    memory_backend: str = "mock"
    hindsight_base_url: str = "http://localhost:8888"
    hindsight_bank_id: str = "adaptive-incident-intelligence"
    hindsight_api_key: str | None = field(default=None, repr=False)
    hindsight_timeout: float = 120.0

    def __post_init__(self):
        if self.memory_backend not in {"mock", "hindsight"}:
            raise ValueError("MEMORY_BACKEND must be mock or hindsight")
        url = urlparse(self.hindsight_base_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("HINDSIGHT_BASE_URL must be an HTTP(S) URL without credentials/query/fragment")
        if not self.hindsight_bank_id.strip():
            raise ValueError("HINDSIGHT_BANK_ID must not be empty")
        if not math.isfinite(self.hindsight_timeout) or self.hindsight_timeout <= 0:
            raise ValueError("HINDSIGHT_TIMEOUT must be finite and positive")

    @classmethod
    def from_env(cls):
        default = Path(__file__).resolve().parent / "data"
        return cls(data_dir=Path(os.environ.get("INCIDENT_DATA_DIR", str(default))).resolve(),
                   memory_backend=os.getenv("MEMORY_BACKEND", "mock"),
                   hindsight_base_url=os.getenv("HINDSIGHT_BASE_URL", "http://localhost:8888").rstrip("/"),
                   hindsight_bank_id=os.getenv("HINDSIGHT_BANK_ID", "adaptive-incident-intelligence"),
                   hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
                   hindsight_timeout=float(os.getenv("HINDSIGHT_TIMEOUT", "120")))
