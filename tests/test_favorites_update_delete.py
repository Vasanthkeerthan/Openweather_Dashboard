from contextlib import contextmanager
from datetime import datetime, timezone

import mysql.connector

from app import create_app
from config import Config


class TestConfig(Config):
    TESTING = True


class FakeCursor:
    def __init__(self, fetchone_results=None, rowcount=1):
        self.fetchone_results = list(fetchone_results or [])
        self.rowcount = rowcount
        self.statements = []

    def execute(self, query, params=None):
        self.statements.append((query, params))

    def fetchone(self):
        return self.fetchone_results.pop(0)


def install_update_cursor(monkeypatch, cursor):
    import routes.favorites_update as update_route

    @contextmanager
    def fake_context(commit=False):
        assert commit is True
        yield cursor

    monkeypatch.setattr(update_route, "get_db_cursor", fake_context)


def install_delete_cursor(monkeypatch, cursor):
    import routes.favorites_delete as delete_route

    @contextmanager
    def fake_context(commit=False):
        assert commit is True
        yield cursor

    monkeypatch.setattr(delete_route, "get_db_cursor", fake_context)


def test_update_favorite_returns_updated_record(monkeypatch):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cursor = FakeCursor(
        fetchone_results=[
            {"id": 4},
            {
                "id": 4,
                "city": "Guntur",
                "country": "IN",
                "nickname": "Work",
                "created_at": created_at,
            },
        ]
    )
    install_update_cursor(monkeypatch, cursor)
    client = create_app(TestConfig).test_client()

    response = client.put(
        "/api/favorites/4",
        json={"city": " Guntur ", "country": "in", "nickname": " Work "},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["favorite"]["city"] == "Guntur"
    assert response.get_json()["data"]["favorite"]["country"] == "IN"
    assert response.get_json()["data"]["favorite"]["created_at"] == created_at.isoformat()
    assert cursor.statements[0][1] == (4,)
    assert cursor.statements[1][1] == ("Guntur", "IN", "Work", 4)


def test_update_favorite_rejects_invalid_input(monkeypatch):
    import routes.favorites_update as update_route

    @contextmanager
    def should_not_connect(**_kwargs):
        raise AssertionError("database should not be accessed")
        yield

    monkeypatch.setattr(update_route, "get_db_cursor", should_not_connect)
    client = create_app(TestConfig).test_client()

    response = client.put("/api/favorites/4", json={"city": "", "country": "IN"})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_input"


def test_update_favorite_returns_404_for_missing_id(monkeypatch):
    cursor = FakeCursor(fetchone_results=[None])
    install_update_cursor(monkeypatch, cursor)
    client = create_app(TestConfig).test_client()

    response = client.put(
        "/api/favorites/404",
        json={"city": "Guntur", "country": "IN"},
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "favorite_not_found"


def test_update_favorite_returns_conflict_for_duplicate(monkeypatch):
    import routes.favorites_update as update_route

    @contextmanager
    def duplicate_context(commit=False):
        assert commit is True
        raise mysql.connector.IntegrityError(errno=1062, msg="duplicate")
        yield

    monkeypatch.setattr(update_route, "get_db_cursor", duplicate_context)
    client = create_app(TestConfig).test_client()

    response = client.put(
        "/api/favorites/4",
        json={"city": "Guntur", "country": "IN"},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "duplicate_favorite"


def test_update_favorite_rejects_invalid_id():
    client = create_app(TestConfig).test_client()

    response = client.put(
        "/api/favorites/0",
        json={"city": "Guntur", "country": "IN"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_id"


def test_delete_favorite_returns_confirmation(monkeypatch):
    cursor = FakeCursor(rowcount=1)
    install_delete_cursor(monkeypatch, cursor)
    client = create_app(TestConfig).test_client()

    response = client.delete("/api/favorites/4")

    assert response.status_code == 200
    assert response.get_json()["data"] == {
        "id": 4,
        "message": "Favorite deleted successfully.",
    }
    assert cursor.statements[0][1] == (4,)


def test_delete_nonexistent_favorite_returns_404(monkeypatch):
    cursor = FakeCursor(rowcount=0)
    install_delete_cursor(monkeypatch, cursor)
    client = create_app(TestConfig).test_client()

    response = client.delete("/api/favorites/404")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "favorite_not_found"


def test_delete_favorite_rejects_invalid_id():
    client = create_app(TestConfig).test_client()

    response = client.delete("/api/favorites/-2")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_id"


def test_delete_favorite_returns_database_error(monkeypatch):
    import routes.favorites_delete as delete_route

    @contextmanager
    def failed_connection(commit=False):
        raise mysql.connector.Error("private database details")
        yield

    monkeypatch.setattr(delete_route, "get_db_cursor", failed_connection)
    client = create_app(TestConfig).test_client()

    response = client.delete("/api/favorites/4")

    assert response.status_code == 500
    assert "private database details" not in response.get_data(as_text=True)
