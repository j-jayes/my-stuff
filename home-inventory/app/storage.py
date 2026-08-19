"""Image storage behind one interface, so tests and the local dev loop need no cloud access."""

import shutil
from pathlib import Path
from typing import BinaryIO, Protocol


class ObjectNotFound(Exception):
    pass


class MediaStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def open(self, key: str) -> tuple[BinaryIO, str, int]:
        """Return a readable stream, its content type, and its size in bytes."""
        ...

    def delete(self, key: str) -> None: ...


class LocalMediaStorage:
    """Writes into a directory on disk. Used by tests and by the hot-reload dev loop."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        # Keys are built by the app from UUIDs, never from user input, but refuse traversal
        # anyway so a future caller cannot turn this into a file-read primitive.
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError(f"key escapes the media root: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_suffix(path.suffix + ".type").write_text(content_type)

    def open(self, key: str) -> tuple[BinaryIO, str, int]:
        path = self._path(key)
        if not path.exists():
            raise ObjectNotFound(key)
        type_file = path.with_suffix(path.suffix + ".type")
        content_type = (
            type_file.read_text() if type_file.exists() else "application/octet-stream"
        )
        return path.open("rb"), content_type, path.stat().st_size

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + ".type").unlink(missing_ok=True)

    def clear(self) -> None:
        shutil.rmtree(self._root, ignore_errors=True)


class GcsMediaStorage:
    """The deployed backend. The bucket stays private; bytes are served through the app so the
    session cookie is what gates access. See research D4 for why not signed URLs.
    """

    def __init__(self, bucket_name: str, project: str | None = None) -> None:
        from google.cloud import storage

        self._bucket = storage.Client(project=project).bucket(bucket_name)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._bucket.blob(key).upload_from_string(data, content_type=content_type)

    def open(self, key: str) -> tuple[BinaryIO, str, int]:
        from google.api_core.exceptions import NotFound

        blob = self._bucket.blob(key)
        try:
            blob.reload()
        except NotFound as exc:
            raise ObjectNotFound(key) from exc
        return blob.open("rb"), blob.content_type or "application/octet-stream", blob.size

    def delete(self, key: str) -> None:
        from google.api_core.exceptions import NotFound

        try:
            self._bucket.blob(key).delete()
        except NotFound:
            # Deleting an item whose object is already gone is a success, not an error.
            pass
