import pytest

import database
from config import Config
from app import create_app


class TestConfig(Config):
    TESTING = True
    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_USER = "test-user"
    MYSQL_PASSWORD = "test-password"
    MYSQL_DATABASE = "weatherhub_db"
    MYSQL_CHARSET = "utf8mb4"


class FakeCursor:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, dictionary=False):
        assert dictionary is True
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def is_connected(self):
        return True

    def close(self):
        self.closed = True


def test_db_cursor_commits_and_closes_resources(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(
        database.mysql.connector, "connect", lambda **_kwargs: connection
    )
    app = create_app(TestConfig)

    with app.app_context():
        with database.get_db_cursor(commit=True):
            pass

    assert connection.committed
    assert connection.cursor_instance.closed
    assert connection.closed


def test_db_cursor_rolls_back_and_closes_resources_on_error(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(
        database.mysql.connector, "connect", lambda **_kwargs: connection
    )
    app = create_app(TestConfig)

    with app.app_context():
        with pytest.raises(ValueError, match="query failed"):
            with database.get_db_cursor(commit=True):
                raise ValueError("query failed")

    assert connection.rolled_back
    assert not connection.committed
    assert connection.cursor_instance.closed
    assert connection.closed
