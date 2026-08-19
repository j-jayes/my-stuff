from app.snapshot import PreconditionFailed


class FakeObjectStore:
    """In-memory stand-in for the GCS object store, with the same generation semantics.

    Real GCS assigns a new generation number on every write and rejects a write whose
    if_generation_match does not equal the current one (0 meaning "must not exist").
    """

    def __init__(self) -> None:
        self._data: bytes | None = None
        self._generation: int | None = None
        self._next_generation = 1000

    def download(self, name: str) -> tuple[bytes, int] | None:
        if self._data is None:
            return None
        return self._data, self._generation

    def upload(self, name: str, data: bytes, if_generation_match: int) -> int:
        current = self._generation or 0
        if if_generation_match != current:
            raise PreconditionFailed(
                f"generation {if_generation_match} does not match current {current}"
            )
        self._next_generation += 1
        self._data = data
        self._generation = self._next_generation
        return self._generation

    def read(self, name: str) -> bytes | None:
        return self._data
