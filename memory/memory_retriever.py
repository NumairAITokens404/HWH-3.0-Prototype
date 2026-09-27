"""Small retrieval facade shared by future agents and services."""

from memory.hindsight_client import HindsightClient, MemoryMatch
from schemas.incident import Incident


def retrieve_history(client: HindsightClient, incident: Incident, limit: int = 5) -> list[MemoryMatch]:
    """Return complete records; never discard failed attempts from matches."""
    return client.retrieve_similar_incidents(incident, limit=limit)
