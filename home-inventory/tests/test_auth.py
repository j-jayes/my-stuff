"""The inventory is a catalogue of a home's contents behind a public URL. Every route that
touches it must be shut to a visitor without a session (FR-020).
"""

import pytest

from tests.conftest import PASSWORD

PROTECTED = [
    ("get", "/api/items"),
    ("post", "/api/items"),
    ("get", "/api/items/anything"),
    ("delete", "/api/items/anything"),
    ("post", "/api/items/suggest"),
    ("get", "/api/items/brands"),
    ("get", "/api/items/similar?name=x"),
    ("get", "/api/rooms"),
    ("post", "/api/rooms"),
    ("get", "/api/categories"),
    ("get", "/api/boards"),
    ("post", "/api/boards"),
    ("get", "/api/boards/anything"),
    ("get", "/api/media/items/x/thumb.webp"),
    ("get", "/api/auth/me"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_every_data_route_is_closed_without_a_session(client, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == 401, f"{method.upper()} {path} was reachable without signing in"


def test_health_is_open_and_says_nothing_about_the_inventory(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_right_password_opens_a_session_that_survives_reloads(client):
    assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 204

    assert client.get("/api/auth/me").json() == {"authenticated": True}
    assert client.get("/api/items").status_code == 200


def test_the_wrong_password_is_refused_without_explaining_why(client):
    response = client.post("/api/auth/login", json={"password": "not it"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password"
    assert client.get("/api/items").status_code == 401


def test_a_forged_cookie_is_rejected(client):
    client.cookies.set("session", "made.up.value")

    assert client.get("/api/items").status_code == 401


def test_signing_out_closes_the_session(signed_in):
    assert signed_in.post("/api/auth/logout").status_code == 204

    assert signed_in.get("/api/items").status_code == 401
