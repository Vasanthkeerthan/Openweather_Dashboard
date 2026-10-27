from app import create_app
from config import Config
import mysql.connector


class TestConfig(Config):
    TESTING = True
    OPENWEATHER_API_KEY = "weather-secret-test-value"
    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_USER = "test-user"
    MYSQL_PASSWORD = "database-secret-test-value"
    MYSQL_DATABASE = "weatherhub_db"


class FakeResponse:
    def __init__(self, status_code, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise ValueError("upstream body contains sensitive information")
        return self.payload


def test_openweather_current_request_resolves_city_and_uses_coordinates(monkeypatch):
    import services.openweather as openweather

    responses = [
        FakeResponse(
            200,
            [
                {
                    "name": "Vijayawada",
                    "state": "Andhra Pradesh",
                    "country": "IN",
                    "lat": 16.5,
                    "lon": 80.6,
                }
            ],
        ),
        FakeResponse(
            200,
            {"main": {"temp": 25}, "weather": [{"description": "clear sky"}]},
        ),
    ]
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params, timeout))
        return responses.pop(0)

    monkeypatch.setattr(openweather.requests, "get", fake_get)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada&country=IN")

    assert response.status_code == 200
    assert len(calls) == 2
    assert calls[0][1] == {
        "q": "Vijayawada,IN",
        "limit": 5,
        "appid": "weather-secret-test-value",
    }
    assert calls[1][1] == {
        "lat": 16.5,
        "lon": 80.6,
        "units": "metric",
        "appid": "weather-secret-test-value",
    }
    assert calls[0][2] == TestConfig.OPENWEATHER_TIMEOUT


def test_openweather_invalid_key_is_sanitized(monkeypatch):
    import services.openweather as openweather

    monkeypatch.setattr(
        openweather.requests, "get", lambda *_args, **_kwargs: FakeResponse(401)
    )
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada&country=IN")

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "weather_service_authentication_failed"
    assert "weather-secret-test-value" not in response.get_data(as_text=True)


def test_openweather_rate_limit_returns_service_unavailable(monkeypatch):
    import services.openweather as openweather

    monkeypatch.setattr(
        openweather.requests, "get", lambda *_args, **_kwargs: FakeResponse(429)
    )
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/forecast?city=Vijayawada&country=IN")

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "weather_service_rate_limited"


def test_openweather_timeout_returns_gateway_timeout(monkeypatch):
    import requests
    import services.openweather as openweather

    def timeout(*_args, **_kwargs):
        raise requests.Timeout("request included an API key")

    monkeypatch.setattr(openweather.requests, "get", timeout)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada&country=IN")

    assert response.status_code == 504
    assert response.get_json()["error"]["code"] == "weather_service_timeout"
    assert "weather-secret-test-value" not in response.get_data(as_text=True)


def test_openweather_connection_failure_returns_service_unavailable(monkeypatch):
    import requests
    import services.openweather as openweather

    def connection_error(*_args, **_kwargs):
        raise requests.ConnectionError("request included an API key")

    monkeypatch.setattr(openweather.requests, "get", connection_error)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada&country=IN")

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "weather_service_unavailable"
    assert "weather-secret-test-value" not in response.get_data(as_text=True)


def test_malformed_openweather_response_returns_bad_gateway(monkeypatch):
    import services.openweather as openweather

    monkeypatch.setattr(
        openweather.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(200, json_error=True),
    )
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada&country=IN")

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "invalid_weather_service_response"
    assert "sensitive information" not in response.get_data(as_text=True)


def test_openweather_rejects_invalid_country_before_request(monkeypatch):
    import services.openweather as openweather

    def should_not_request(*_args, **_kwargs):
        raise AssertionError("upstream should not be called")

    monkeypatch.setattr(openweather.requests, "get", should_not_request)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada&country=India")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_parameters"


def test_openweather_resolves_city_without_country(monkeypatch):
    import services.openweather as openweather

    responses = [
        FakeResponse(
            200,
            [
                {
                    "name": "Vijayawada",
                    "state": "Andhra Pradesh",
                    "country": "IN",
                    "lat": 16.5,
                    "lon": 80.6,
                }
            ],
        ),
        FakeResponse(
            200,
            {"main": {"temp": 25}, "weather": [{"description": "clear sky"}]},
        ),
    ]
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params, timeout))
        return responses.pop(0)

    monkeypatch.setattr(openweather.requests, "get", fake_get)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada")

    assert response.status_code == 200
    assert calls[0][1] == {
        "q": "Vijayawada",
        "limit": 5,
        "appid": "weather-secret-test-value",
    }


def test_unconfigured_database_returns_sanitized_unavailable_response():
    class MissingDatabaseConfig(TestConfig):
        MYSQL_USER = ""

    client = create_app(MissingDatabaseConfig).test_client()

    response = client.get("/api/favorites")

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "database_unavailable"
    assert "database-secret-test-value" not in response.get_data(as_text=True)


def test_database_connection_failure_returns_unavailable(monkeypatch):
    import database

    def failed_connection(**_kwargs):
        raise mysql.connector.Error(errno=2003, msg="private host details")

    monkeypatch.setattr(database.mysql.connector, "connect", failed_connection)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/favorites")

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "database_unavailable"
    assert "private host details" not in response.get_data(as_text=True)


def test_http_errors_use_json_responses():
    client = create_app(TestConfig).test_client()

    not_found = client.get("/api/not-a-route")
    method_not_allowed = client.post("/api/health")

    assert not_found.status_code == 404
    assert not_found.get_json()["error"]["code"] == "not_found"
    assert method_not_allowed.status_code == 405
    assert method_not_allowed.get_json()["error"]["code"] == "http_error"


def test_unexpected_errors_do_not_expose_details_in_response_or_logs(caplog):
    app = create_app(TestConfig)

    @app.get("/api/test/unexpected")
    def raise_unexpected_error():
        raise RuntimeError("weather-secret-test-value")

    with caplog.at_level("ERROR", logger=app.logger.name):
        response = app.test_client().get("/api/test/unexpected")

    assert response.status_code == 500
    assert "weather-secret-test-value" not in response.get_data(as_text=True)
    assert "weather-secret-test-value" not in caplog.text
