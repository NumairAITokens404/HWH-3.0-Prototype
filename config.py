"""Small environment-based configuration for the offline scaffold."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path

    @classmethod
    def from_env(cls):
        default = Path(__file__).resolve().parent / "data"
        return cls(data_dir=Path(os.environ.get("INCIDENT_DATA_DIR", str(default))).resolve())
