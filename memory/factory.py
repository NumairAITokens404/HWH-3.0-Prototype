"""Select an explicit memory backend; errors never switch backends silently."""

from dataclasses import replace
from pathlib import Path
import re

from config import Settings
from memory.hindsight_client import HindsightClient, MockHindsightClient


def _safe_namespace(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    if not cleaned:
        raise ValueError("Memory namespace must contain a letter or number")
    return cleaned[:80]


def create_memory_client(settings: Settings, namespace: str | None = None) -> HindsightClient:
    """Create the configured backend, optionally isolated for one dashboard run."""
    if namespace:
        namespace = _safe_namespace(namespace)
        if settings.memory_backend == "hindsight":
            settings = replace(settings, hindsight_bank_id=f"{settings.hindsight_bank_id}-{namespace}")
        elif settings.memory_backend == "sqlite":
            path = Path(settings.sqlite_path)
            settings = replace(settings, sqlite_path=path.with_name(f"{path.stem}-{namespace}{path.suffix}"))
    if settings.memory_backend == "mock":
        return MockHindsightClient()
    if settings.memory_backend == "sqlite":
        from memory.sqlite_client import SQLiteMemoryClient
        return SQLiteMemoryClient(settings.sqlite_path)
    from memory.hindsight_adapter import HindsightMemoryClient
    return HindsightMemoryClient(settings)
