"""Select an explicit memory backend; errors never switch backends silently."""

from config import Settings
from memory.hindsight_client import HindsightClient, MockHindsightClient


def create_memory_client(settings: Settings) -> HindsightClient:
    if settings.memory_backend == "mock":
        return MockHindsightClient()
    if settings.memory_backend == "sqlite":
        from memory.sqlite_client import SQLiteMemoryClient
        return SQLiteMemoryClient(settings.sqlite_path)
    from memory.hindsight_adapter import HindsightMemoryClient
    return HindsightMemoryClient(settings)
