"""Process-wide cart/order store (swap this provider to use another backend)."""

from .services.store import MemoryStore

_store = MemoryStore()


def get_store() -> MemoryStore:
    return _store
