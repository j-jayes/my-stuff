"""Persistence for a SQLite database living on an ephemeral filesystem.

Cloud Run gives the container a tmpfs that disappears when the instance does, so the database
is restored from object storage on boot and written back after every mutating request. Writes
carry the GCS generation number we last saw; if it no longer matches, another instance has
written since we read and ours is refused rather than silently clobbering theirs.

See specs/001-home-inventory/research.md D3 for why this replaced Litestream.
"""

from pathlib import Path
from typing import Protocol

try:  # pragma: no cover - exercised only when the GCS client is installed
    from google.api_core.exceptions import PreconditionFailed
except ImportError:  # pragma: no cover

    class PreconditionFailed(Exception):  # type: ignore[no-redef]
        pass


class StaleSnapshotError(Exception):
    """Raised when the snapshot in storage moved on without us."""


class ObjectStore(Protocol):
    def download(self, name: str) -> tuple[bytes, int] | None: ...

    def upload(self, name: str, data: bytes, if_generation_match: int) -> int: ...


class GcsObjectStore:
    def __init__(self, bucket_name: str, project: str | None = None) -> None:
        from google.cloud import storage

        self._bucket = storage.Client(project=project).bucket(bucket_name)

    def download(self, name: str) -> tuple[bytes, int] | None:
        from google.api_core.exceptions import NotFound

        blob = self._bucket.blob(name)
        try:
            data = blob.download_as_bytes()
        except NotFound:
            return None
        return data, blob.generation

    def upload(self, name: str, data: bytes, if_generation_match: int) -> int:
        blob = self._bucket.blob(name)
        blob.upload_from_string(
            data,
            content_type="application/octet-stream",
            if_generation_match=if_generation_match,
        )
        return blob.generation


class DatabaseSnapshot:
    """Ties one local database file to one object in storage.

    A store of None disables snapshotting entirely, which is what local development uses.
    """

    def __init__(self, store: ObjectStore | None, object_name: str, path: Path) -> None:
        self._store = store
        self._object_name = object_name
        self._path = Path(path)
        self.generation: int | None = None

    @property
    def enabled(self) -> bool:
        return self._store is not None

    def restore(self) -> None:
        if self._store is None:
            return
        found = self._store.download(self._object_name)
        if found is None:
            # Nothing has ever been snapshotted; the app will create the database itself.
            return
        data, generation = found
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(data)
        self.generation = generation

    def save(self) -> None:
        if self._store is None:
            return
        # generation 0 is GCS's way of saying "this object must not already exist".
        expected = self.generation if self.generation is not None else 0
        try:
            self.generation = self._store.upload(
                self._object_name, self._path.read_bytes(), if_generation_match=expected
            )
        except PreconditionFailed as exc:
            raise StaleSnapshotError(
                "Another instance wrote to the database since this one last read it. "
                "This instance's copy is stale and the write was refused."
            ) from exc
