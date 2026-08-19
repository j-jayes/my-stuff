import pytest
from fastapi.testclient import TestClient

from app import db, deps
from app.config import Settings, get_settings
from app.main import app
from app.storage import LocalMediaStorage

PASSWORD = "test-password"


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    """Configure the app through the environment, so that every code path reaching for
    get_settings() — including the lifespan handler, which does not go through FastAPI's
    dependency overrides — sees the test configuration.
    """
    env = {
        "APP_PASSWORD": PASSWORD,
        "SESSION_SECRET": "test-secret",
        "STORAGE_BACKEND": "local",
        "LOCAL_MEDIA_DIR": str(tmp_path / "media"),
        "DB_PATH": str(tmp_path / "test.sqlite"),
        "DB_BUCKET": "",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def client(settings) -> TestClient:
    """A real app over a real SQLite file, with images on local disk. No cloud access."""
    db.reset_for_tests()
    with TestClient(app) as test_client:
        # The lifespan has now initialised the database and storage from the test settings.
        assert str(db._snapshot._path) == settings.db_path  # noqa: SLF001 - guards the isolation
        yield test_client
    db.reset_for_tests()


@pytest.fixture
def signed_in(client) -> TestClient:
    response = client.post("/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 204
    return client


@pytest.fixture
def rooms(signed_in) -> dict[str, str]:
    return {r["name"]: r["id"] for r in signed_in.get("/api/rooms").json()}


@pytest.fixture
def categories(signed_in) -> dict[str, str]:
    return {c["name"]: c["id"] for c in signed_in.get("/api/categories").json()}


@pytest.fixture
def local_storage(settings) -> LocalMediaStorage:
    return LocalMediaStorage(settings.local_media_dir)


@pytest.fixture
def photo() -> bytes:
    """A tiny real PNG, so thumbnail generation runs for real rather than being stubbed."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), (120, 90, 60)).save(buffer, "PNG")
    return buffer.getvalue()


__all__ = ["deps"]
