"""Select an explicit memory backend; errors never switch backends silently."""

from config import Settings
from memory.hindsight_client import HindsightClient, MockHindsightClient


def create_memory_client(settings: Settings) -> HindsightClient:
    if settings.memory_backend == "mock":
        return MockHindsightClient()
    from memory.hindsight_adapter import HindsightMemoryClient
    return HindsightMemoryClient(settings)
