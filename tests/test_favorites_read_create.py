from contextlib import contextmanager
from datetime import datetime, timezone

import mysql.connector

from app import create_app
from config import Config


class TestConfig(Config):
    TESTING = True


class FakeCursor:
    def __init__(self, fetchone=None, fetchall=None, lastrowid=1):
        self.fetchone_result = fetchone
        self.fetchall_result = fetchall or []
        self.lastrowid = lastrowid
        self.statements = []

    def execute(self, query, params=None):
        self.statements.append((query, params))

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result


def install_fake_cursor(monkeypatch, cursor, commit_expected=None):
    import routes.favorites_create as create_route
    import routes.favorites_read as read_route

    @contextmanager
    def fake_context(commit=False):
        if commit_expected is not None:
            assert commit is commit_expected
        yield cursor

    monkeypatch.setattr(create_route, "get_db_cursor", fake_context)
    monkeypatch.setattr(read_route, "get_db_cursor", fake_context)
    return create_route, read_route


def test_create_favorite_normalizes_and_returns_record(monkeypatch):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cursor = FakeCursor(
        fetchone={
            "id": 7,
            "city": "Vijayawada",
            "country": "IN",
            "nickname": "Home",
            "created_at": created_at,
        },
        lastrowid=7,
    )
    create_route, _ = install_fake_cursor(monkeypatch, cursor, commit_expected=True)
    client = create_app(TestConfig).test_client()

    response = client.post(
        "/api/favorites",
        json={"city": "  Vijayawada ", "country": "in", "nickname": " Home "},
    )

    assert response.status_code == 201
    assert response.get_json()["data"]["favorite"] == {
        "id": 7,
        "city": "Vijayawada",
        "country": "IN",
        "nickname": "Home",
        "created_at": created_at.isoformat(),
    }
    assert cursor.statements[0][1] == ("Vijayawada", "IN", "Home")


def test_create_favorite_rejects_missing_fields():
    client = create_app(TestConfig).test_client()

    response = client.post("/api/favorites", json={"city": "Vijayawada"})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_input"


def test_create_favorite_rejects_malformed_json():
    client = create_app(TestConfig).test_client()

    response = client.post(
        "/api/favorites",
        data="{malformed",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_json"


def test_create_favorite_returns_conflict_for_duplicate(monkeypatch):
    import routes.favorites_create as create_route

    @contextmanager
    def duplicate_context(commit=False):
        assert commit is True
        raise mysql.connector.IntegrityError(errno=1062, msg="duplicate")
        yield

    monkeypatch.setattr(create_route, "get_db_cursor", duplicate_context)
    client = create_app(TestConfig).test_client()

    response = client.post(
        "/api/favorites",
        json={"city": "Vijayawada", "country": "IN"},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "duplicate_favorite"


def test_read_all_favorites_returns_empty_list(monkeypatch):
    cursor = FakeCursor(fetchall=[])
    _, read_route = install_fake_cursor(monkeypatch, cursor)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/favorites")

    assert response.status_code == 200
    assert response.get_json()["data"]["favorites"] == []


def test_read_all_favorites_serializes_rows(monkeypatch):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cursor = FakeCursor(
        fetchall=[
            {
                "id": 3,
                "city": "Vijayawada",
                "country": "IN",
                "nickname": None,
                "created_at": created_at,
            }
        ]
    )
    install_fake_cursor(monkeypatch, cursor)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/favorites")

    assert response.status_code == 200
    assert response.get_json()["data"]["favorites"][0]["created_at"] == created_at.isoformat()


def test_read_existing_favorite(monkeypatch):
    cursor = FakeCursor(
        fetchone={
            "id": 3,
            "city": "Vijayawada",
            "country": "IN",
            "nickname": None,
            "created_at": None,
        }
    )
    install_fake_cursor(monkeypatch, cursor)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/favorites/3")

    assert response.status_code == 200
    assert response.get_json()["data"]["favorite"]["id"] == 3
    assert cursor.statements[0][1] == (3,)


def test_read_nonexistent_favorite_returns_404(monkeypatch):
    cursor = FakeCursor(fetchone=None)
    install_fake_cursor(monkeypatch, cursor)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/favorites/999")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "favorite_not_found"


def test_read_favorite_rejects_invalid_id(monkeypatch):
    import routes.favorites_read as read_route

    @contextmanager
    def should_not_connect():
        raise AssertionError("database should not be accessed")
        yield

    monkeypatch.setattr(read_route, "get_db_cursor", should_not_connect)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/favorites/0")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_id"


def test_favorites_read_returns_database_error(monkeypatch):
    import routes.favorites_read as read_route

    @contextmanager
    def failed_connection():
        raise mysql.connector.Error("private database details")
        yield

    monkeypatch.setattr(read_route, "get_db_cursor", failed_connection)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/favorites")

    assert response.status_code == 500
    assert "private database details" not in response.get_data(as_text=True)
