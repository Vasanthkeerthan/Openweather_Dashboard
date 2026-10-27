from config import Config
from app import create_app
from services.openweather import WeatherServiceError
import pytest
from urllib.parse import urlencode


class TestConfig(Config):
    TESTING = True
    OPENWEATHER_API_KEY = "test-key"


def test_health_check_succeeds():
    client = create_app(TestConfig).test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {"status": "healthy"},
    }


def test_current_weather_returns_upstream_data(monkeypatch):
    from routes import weather_current

    expected = {"main": {"temp": 24}, "weather": [{"description": "clear sky"}]}
    monkeypatch.setattr(weather_current, "get_current_weather", lambda *_: expected)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada&country=IN")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "data": expected}


def test_current_weather_rejects_missing_parameters(monkeypatch):
    from routes import weather_current

    monkeypatch.setattr(
        weather_current,
        "get_current_weather",
        lambda *_: (_ for _ in ()).throw(AssertionError("service should not be called")),
    )
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "missing_parameters"


def test_current_weather_allows_city_without_country(monkeypatch):
    from routes import weather_current

    expected = {"main": {"temp": 24}, "weather": [{"description": "clear sky"}]}
    requested = []
    monkeypatch.setattr(
        weather_current,
        "get_current_weather",
        lambda city, country, state="": requested.append((city, country, state)) or expected,
    )
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Vijayawada")

    assert response.status_code == 200
    assert response.get_json()["data"] == expected
    assert requested == [("Vijayawada", "", "")]


def test_current_weather_returns_not_found_for_invalid_city(monkeypatch):
    from routes import weather_current

    def raise_city_not_found(*_args):
        raise WeatherServiceError(404, "city_not_found", "The requested city could not be found.")

    monkeypatch.setattr(weather_current, "get_current_weather", raise_city_not_found)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=NoSuchCity&country=IN")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "city_not_found"


def test_forecast_returns_upstream_data(monkeypatch):
    from routes import weather_forecast

    expected = {"city": {"name": "Vijayawada"}, "list": []}
    monkeypatch.setattr(weather_forecast, "get_weather_forecast", lambda *_: expected)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/forecast?city=Vijayawada&country=IN")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "data": expected}


def test_forecast_returns_not_found_for_invalid_city(monkeypatch):
    from routes import weather_forecast

    def raise_city_not_found(*_args):
        raise WeatherServiceError(404, "city_not_found", "The requested city could not be found.")

    monkeypatch.setattr(weather_forecast, "get_weather_forecast", raise_city_not_found)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/forecast?city=NoSuchCity&country=IN")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "city_not_found"


def test_forecast_rejects_missing_city():
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/forecast?country=IN")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "missing_parameters"


def test_forecast_allows_city_without_country(monkeypatch):
    from routes import weather_forecast

    expected = {"city": {"name": "Vijayawada"}, "list": []}
    requested = []
    monkeypatch.setattr(
        weather_forecast,
        "get_weather_forecast",
        lambda city, country, state="", latitude=None, longitude=None: requested.append(
            (city, country, state, latitude, longitude)
        )
        or expected,
    )
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/forecast?city=Vijayawada")

    assert response.status_code == 200
    assert response.get_json()["data"] == expected
    assert requested == [("Vijayawada", "", "", None, None)]


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


@pytest.mark.parametrize(
    ("city", "state", "latitude", "longitude"),
    [
        ("Mumbai", "Maharashtra", 19.076, 72.8777),
        ("Bengaluru", "Karnataka", 12.9716, 77.5946),
        ("Vijayawada", "Andhra Pradesh", 16.5062, 80.648),
    ],
)
def test_current_and_forecast_use_same_resolved_city_metadata(
    monkeypatch, city, state, latitude, longitude
):
    from services import openweather

    geocoding_result = [
        {
            "name": "Khetwadi",
            "state": state,
            "country": "IN",
            "lat": latitude + 0.01,
            "lon": longitude + 0.01,
        },
        {
            "name": city,
            "state": state,
            "country": "IN",
            "lat": latitude,
            "lon": longitude,
        },
    ]
    request_log = []

    def fake_get(url, params, timeout):
        request_log.append((url, params.copy(), timeout))
        if url.endswith("/geo/1.0/direct"):
            return FakeResponse(200, geocoding_result)
        if url.endswith("/data/2.5/weather"):
            return FakeResponse(
                200,
                {
                    "name": "Khetwadi",
                    "coord": {"lat": 0, "lon": 0},
                    "sys": {"country": "XX"},
                    "main": {
                        "temp": 27.5,
                        "feels_like": 29.0,
                        "humidity": 71,
                        "pressure": 1008,
                    },
                    "wind": {"speed": 3.2},
                    "visibility": 9500,
                    "weather": [{"description": "scattered clouds", "icon": "03d"}],
                    "dt": 1_800_000_000,
                    "timezone": 19800,
                },
            )
        return FakeResponse(
            200,
            {
                "city": {
                    "name": "Khetwadi",
                    "country": "XX",
                    "coord": {"lat": 0, "lon": 0},
                    "timezone": 19800,
                },
                "list": [
                    {
                        "dt": 1_800_000_000,
                        "main": {"temp": 27.5},
                        "weather": [{"description": "scattered clouds"}],
                    }
                ],
            },
        )

    monkeypatch.setattr(openweather.requests, "get", fake_get)
    client = create_app(TestConfig).test_client()

    current_response = client.get(
        f"/api/weather/current?city={city}&country=IN"
    )
    forecast_query = urlencode(
        {
            "city": city,
            "country": "IN",
            "state": state,
            "latitude": latitude,
            "longitude": longitude,
        }
    )
    forecast_response = client.get(f"/api/weather/forecast?{forecast_query}")

    assert current_response.status_code == forecast_response.status_code == 200
    current = current_response.get_json()["data"]
    forecast = forecast_response.get_json()["data"]
    expected_location = {
        "city": city,
        "state": state,
        "country": "IN",
        "latitude": latitude,
        "longitude": longitude,
    }
    assert {key: current[key] for key in expected_location} == expected_location
    assert forecast["location"] == expected_location
    assert current["name"] == city
    assert current["main"] == {
        "temp": 27.5,
        "feels_like": 29.0,
        "humidity": 71,
        "pressure": 1008,
    }
    assert current["wind"]["speed"] == 3.2
    assert current["visibility"] == 9500
    assert current["weather"][0]["description"] == "scattered clouds"
    assert forecast["city"]["name"] == city
    assert forecast["city"]["country"] == "IN"
    assert forecast["list"][0]["main"]["temp"] == 27.5

    weather_requests = [
        params
        for url, params, _timeout in request_log
        if url.endswith(("/data/2.5/weather", "/data/2.5/forecast"))
    ]
    assert len(weather_requests) == 2
    assert all(params["lat"] == latitude for params in weather_requests)
    assert all(params["lon"] == longitude for params in weather_requests)
    geocoding_requests = [
        params for url, params, _timeout in request_log if "/geo/" in url
    ]
    assert len(geocoding_requests) == 1
    assert all(params["limit"] == 5 for params in geocoding_requests)
    assert all(params["q"].endswith(",IN") for params in geocoding_requests)


def test_geocoding_rejects_a_result_that_does_not_match_requested_city(monkeypatch):
    from services import openweather

    requests_made = []

    def fake_get(url, params, timeout):
        requests_made.append(url)
        return FakeResponse(
            200,
            [
                {
                    "name": "Khetwadi",
                    "state": "Maharashtra",
                    "country": "IN",
                    "lat": 18.97,
                    "lon": 72.83,
                }
            ],
        )

    monkeypatch.setattr(openweather.requests, "get", fake_get)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Mumbai&country=IN")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "city_not_found"
    assert len(requests_made) == 1


def test_geocoding_requires_state_when_city_is_ambiguous(monkeypatch):
    from services import openweather

    locations = [
        {
            "name": "Springfield",
            "state": "Illinois",
            "country": "US",
            "lat": 39.78,
            "lon": -89.64,
        },
        {
            "name": "Springfield",
            "state": "Missouri",
            "country": "US",
            "lat": 37.21,
            "lon": -93.29,
        },
    ]

    def fake_get(url, params, timeout):
        if url.endswith("/geo/1.0/direct"):
            return FakeResponse(200, locations)
        if params["lat"] == 39.78:
            reverse_location = locations[0]
        else:
            reverse_location = locations[1]
        return FakeResponse(200, [reverse_location])

    monkeypatch.setattr(openweather.requests, "get", fake_get)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Springfield")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ambiguous_city"


def test_reverse_geocoding_rejects_an_unrelated_duplicate_city_candidate(monkeypatch):
    from services import openweather

    locations = [
        {
            "name": "Hyderabad",
            "state": "Telangana",
            "country": "IN",
            "lat": 17.360589,
            "lon": 78.4740613,
        },
        {
            "name": "Hyderabad",
            "state": "Telangana",
            "country": "IN",
            "lat": 17.6687464,
            "lon": 77.5898867,
        },
    ]
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params.copy()))
        if url.endswith("/geo/1.0/direct"):
            return FakeResponse(200, locations)
        if url.endswith("/geo/1.0/reverse"):
            if params["lat"] == locations[0]["lat"]:
                return FakeResponse(200, [locations[0]])
            return FakeResponse(
                200,
                [
                    {
                        "name": "Zahirabad mandal",
                        "state": "Telangana",
                        "country": "IN",
                        "lat": 17.679403,
                        "lon": 77.6153076,
                    }
                ],
            )
        return FakeResponse(
            200,
            {"main": {"temp": 28}, "weather": [{"description": "clear sky"}]},
        )

    monkeypatch.setattr(openweather.requests, "get", fake_get)
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Hyderabad&country=IN")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["city"] == "Hyderabad"
    assert data["state"] == "Telangana"
    assert data["latitude"] == locations[0]["lat"]
    assert data["longitude"] == locations[0]["lon"]
    reverse_calls = [
        params for url, params in calls if url.endswith("/geo/1.0/reverse")
    ]
    assert len(reverse_calls) == 2


@pytest.mark.parametrize(
    ("city", "primary_state", "primary_latitude", "primary_longitude", "other_state"),
    [
        ("Mumbai", "Maharashtra", 18.9733536, 72.8281049, "Maharashtra"),
        ("Jaipur", "Rajasthan", 26.9154576, 75.8189817, "West Bengal"),
    ],
)
def test_country_filter_selects_top_ranked_exact_city_candidate(
    monkeypatch, city, primary_state, primary_latitude, primary_longitude, other_state
):
    from services import openweather

    locations = [
        {
            "name": city,
            "state": primary_state,
            "country": "IN",
            "lat": primary_latitude,
            "lon": primary_longitude,
        },
        {
            "name": city,
            "state": other_state,
            "country": "IN",
            "lat": primary_latitude + 0.1,
            "lon": primary_longitude + 0.1,
        },
    ]

    def fake_get(url, params, timeout):
        if url.endswith("/geo/1.0/direct"):
            return FakeResponse(200, locations)
        if url.endswith("/geo/1.0/reverse"):
            if params["lat"] == locations[0]["lat"]:
                reverse_name = (
                    "Jaipur Municipal Corporation"
                    if city == "Jaipur"
                    else city
                )
                return FakeResponse(
                    200,
                    [
                        {
                            "name": reverse_name,
                            "state": primary_state,
                            "country": "IN",
                        }
                    ],
                )
            return FakeResponse(
                200,
                [
                    {
                        "name": city,
                        "state": other_state,
                        "country": "IN",
                    }
                ],
            )
        return FakeResponse(
            200,
            {"main": {"temp": 28}, "weather": [{"description": "clear sky"}]},
        )

    monkeypatch.setattr(openweather.requests, "get", fake_get)
    client = create_app(TestConfig).test_client()

    response = client.get(f"/api/weather/current?city={city}&country=IN")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["city"] == city
    assert data["state"] == primary_state
    assert data["latitude"] == primary_latitude
    assert data["longitude"] == primary_longitude


def test_state_parameter_disambiguates_duplicate_city_names(monkeypatch):
    from services import openweather

    locations = [
        {
            "name": "Springfield",
            "state": "Illinois",
            "country": "US",
            "lat": 39.78,
            "lon": -89.64,
        },
        {
            "name": "Springfield",
            "state": "Missouri",
            "country": "US",
            "lat": 37.21,
            "lon": -93.29,
        },
    ]
    requests_made = []

    def fake_get(url, params, timeout):
        requests_made.append(params.copy())
        if url.endswith("/geo/1.0/direct"):
            return FakeResponse(200, locations)
        return FakeResponse(
            200,
            {"main": {"temp": 20}, "weather": [{"description": "clear sky"}]},
        )

    monkeypatch.setattr(openweather.requests, "get", fake_get)
    client = create_app(TestConfig).test_client()

    response = client.get(
        "/api/weather/current?city=Springfield&country=US&state=Illinois"
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["location"]["state"] == "Illinois"
    assert requests_made[0]["q"] == "Springfield,Illinois,US"


@pytest.mark.parametrize(
    ("upstream_status", "expected_status", "expected_code"),
    [
        (401, 502, "weather_service_authentication_failed"),
        (429, 503, "weather_service_rate_limited"),
        (503, 503, "weather_service_unavailable"),
    ],
)
def test_current_weather_reports_openweather_failures(
    monkeypatch, upstream_status, expected_status, expected_code
):
    from services import openweather

    monkeypatch.setattr(
        openweather.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(upstream_status, {}),
    )
    client = create_app(TestConfig).test_client()

    response = client.get("/api/weather/current?city=Mumbai&country=IN")

    assert response.status_code == expected_status
    assert response.get_json()["error"]["code"] == expected_code


def test_weather_endpoints_reject_blank_city():
    client = create_app(TestConfig).test_client()

    for endpoint in ("current", "forecast"):
        response = client.get(f"/api/weather/{endpoint}?city=%20%20")

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "missing_parameters"
