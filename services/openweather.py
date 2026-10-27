import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from numbers import Real

import requests
from flask import current_app


class WeatherServiceError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ResolvedLocation:
    city: str
    state: str
    country: str
    latitude: float
    longitude: float


def _request_json(path, params):
    api_key = current_app.config.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise WeatherServiceError(
            503,
            "weather_service_unavailable",
            "The weather service is not configured.",
        )

    request_params = dict(params)
    request_params["appid"] = api_key
    url = f"{current_app.config['OPENWEATHER_BASE_URL']}{path}"
    try:
        response = requests.get(
            url,
            params=request_params,
            timeout=current_app.config["OPENWEATHER_TIMEOUT"],
        )
    except requests.Timeout as error:
        raise WeatherServiceError(
            504, "weather_service_timeout", "The weather service timed out."
        ) from error
    except requests.ConnectionError as error:
        raise WeatherServiceError(
            503,
            "weather_service_unavailable",
            "The weather service could not be reached.",
        ) from error
    except requests.RequestException as error:
        raise WeatherServiceError(
            502, "weather_service_error", "The weather service request failed."
        ) from error

    if response.status_code == 401:
        raise WeatherServiceError(
            502,
            "weather_service_authentication_failed",
            "The weather service rejected its configured credentials.",
        )
    if response.status_code == 429:
        raise WeatherServiceError(
            503,
            "weather_service_rate_limited",
            "The weather service rate limit was reached.",
        )
    if response.status_code >= 500:
        raise WeatherServiceError(
            503, "weather_service_unavailable", "The weather service is unavailable."
        )
    if response.status_code >= 400:
        raise WeatherServiceError(
            502, "weather_service_error", "The weather service returned an error."
        )

    try:
        return response.json()
    except (ValueError, requests.exceptions.JSONDecodeError) as error:
        raise WeatherServiceError(
            502,
            "invalid_weather_service_response",
            "The weather service returned an invalid response.",
        ) from error


def _normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _identity(value):
    return _normalize(value).casefold()


def _reverse_matches(location, city, country, state):
    result = _request_json(
        "/geo/1.0/reverse",
        {"lat": location["lat"], "lon": location["lon"], "limit": 1},
    )
    if not isinstance(result, list):
        raise WeatherServiceError(
            502,
            "invalid_weather_service_response",
            "The weather service returned an invalid reverse-geocoding response.",
        )
    if not result:
        return False

    reverse_location = result[0]
    if not isinstance(reverse_location, dict):
        raise WeatherServiceError(
            502,
            "invalid_weather_service_response",
            "The weather service returned an invalid reverse-geocoding response.",
        )
    if (
        not isinstance(reverse_location.get("name"), str)
        or not isinstance(reverse_location.get("country"), str)
        or (
            _identity(reverse_location["name"]) != _identity(city)
            and not _identity(reverse_location["name"]).startswith(
                f"{_identity(city)} "
            )
        )
        or reverse_location["country"].strip().upper() != country
    ):
        return False
    return not state or (
        isinstance(reverse_location.get("state"), str)
        and _identity(reverse_location["state"]) == _identity(state)
    )


def _resolve_city(city, country="", state=""):
    city = _normalize(city)
    country = country.strip().upper()
    state = _normalize(state)

    if (
        not city
        or len(city) > 120
        or (country and not re.fullmatch(r"[A-Z]{2}", country))
        or len(state) > 120
    ):
        raise WeatherServiceError(
            400,
            "invalid_parameters",
            "City and state must be at most 120 characters, and country, when supplied, must be a two-letter code.",
        )

    query = ",".join(part for part in (city, state, country) if part)
    result = _request_json(
        "/geo/1.0/direct",
        {"q": query, "limit": 5},
    )
    if not isinstance(result, list):
        raise WeatherServiceError(
            502,
            "invalid_weather_service_response",
            "The weather service returned an invalid location response.",
        )

    matches = []
    for location in result:
        if not isinstance(location, dict):
            raise WeatherServiceError(
                502,
                "invalid_weather_service_response",
                "The weather service returned an invalid location response.",
            )
        if not isinstance(location.get("name"), str):
            continue
        if _identity(location["name"]) != _identity(city):
            continue
        if country and (
            not isinstance(location.get("country"), str)
            or location["country"].strip().upper() != country
        ):
            continue
        if state and (
            not isinstance(location.get("state"), str)
            or _identity(location["state"]) != _identity(state)
        ):
            continue
        matches.append(location)

    if not matches:
        raise WeatherServiceError(
            404, "city_not_found", "The requested city could not be found."
        )

    for location in matches:
        latitude = location.get("lat")
        longitude = location.get("lon")
        if (
            isinstance(latitude, bool)
            or not isinstance(latitude, Real)
            or isinstance(longitude, bool)
            or not isinstance(longitude, Real)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
            or not isinstance(location.get("country"), str)
            or not isinstance(location.get("state", ""), str)
        ):
            raise WeatherServiceError(
                502,
                "invalid_weather_service_response",
                "The weather service returned invalid location data.",
            )

    if len(matches) > 1:
        matches = [
            location
            for location in matches
            if _reverse_matches(location, city, country or location["country"].upper(), state)
        ]
        if not matches:
            raise WeatherServiceError(
                404, "city_not_found", "The requested city could not be found."
            )

    unique_matches = {
        (
            location["country"].strip().upper(),
            location.get("state", ""),
            location.get("lat"),
            location.get("lon"),
        ): location
        for location in matches
    }
    if len(unique_matches) > 1 and not country:
        raise WeatherServiceError(
            400,
            "ambiguous_city",
            "The city name matches multiple locations. Supply a country code and, if needed, a state or region.",
        )

    # OpenWeather returns candidates in relevance order. With a country filter,
    # prefer its first exact-name candidate instead of treating duplicate
    # coordinates or smaller same-name localities as a failed city lookup.
    location = next(iter(unique_matches.values()))
    latitude = location.get("lat")
    longitude = location.get("lon")

    return ResolvedLocation(
        city=location["name"],
        state=location.get("state", ""),
        country=location["country"].upper(),
        latitude=latitude,
        longitude=longitude,
    )


def _location_from_coordinates(city, country, state, latitude, longitude):
    city = _normalize(city)
    country = country.strip().upper()
    state = _normalize(state)
    if (
        not city
        or len(city) > 120
        or not re.fullmatch(r"[A-Z]{2}", country)
        or len(state) > 120
    ):
        raise WeatherServiceError(
            400,
            "invalid_parameters",
            "Resolved city, country, and state metadata is invalid.",
        )

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError) as error:
        raise WeatherServiceError(
            400, "invalid_parameters", "Resolved coordinates must be numeric."
        ) from error
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise WeatherServiceError(
            400, "invalid_parameters", "Resolved coordinates are outside valid ranges."
        )

    return ResolvedLocation(city, state, country, latitude, longitude)


def _attach_location(result, location, endpoint):
    metadata = asdict(location)
    result["location"] = metadata

    if endpoint.endswith("/weather"):
        result.update(metadata)
        result["name"] = location.city
        result["coord"] = {"lat": location.latitude, "lon": location.longitude}
        system = result.get("sys")
        if isinstance(system, dict):
            system["country"] = location.country
    else:
        forecast_city = result["city"]
        forecast_city["name"] = location.city
        forecast_city["country"] = location.country
        forecast_city["coord"] = {
            "lat": location.latitude,
            "lon": location.longitude,
        }
        forecast_city.update(metadata)
    return result


def _get_weather(city, country, endpoint, state="", location=None):
    if location is None:
        location = _resolve_city(city, country, state)
    result = _request_json(
        endpoint,
        {
            "lat": location.latitude,
            "lon": location.longitude,
            "units": "metric",
        },
    )
    if not isinstance(result, dict):
        raise WeatherServiceError(
            502,
            "invalid_weather_service_response",
            "The weather service returned an invalid weather response.",
        )
    if endpoint.endswith("/weather"):
        valid_response = isinstance(result.get("main"), dict) and isinstance(
            result.get("weather"), list
        )
    else:
        valid_response = isinstance(result.get("list"), list) and isinstance(
            result.get("city"), dict
        )
    if not valid_response:
        raise WeatherServiceError(
            502,
            "invalid_weather_service_response",
            "The weather service returned an incomplete weather response.",
        )
    return _attach_location(result, location, endpoint)


def get_current_weather(city, country, state=""):
    return _get_weather(city, country, "/data/2.5/weather", state)


def get_weather_forecast(
    city, country, state="", latitude=None, longitude=None
):
    if latitude is None and longitude is None:
        location = None
    elif latitude is None or longitude is None:
        raise WeatherServiceError(
            400,
            "invalid_parameters",
            "Both resolved coordinates are required for a forecast request.",
        )
    else:
        location = _location_from_coordinates(
            city, country, state, latitude, longitude
        )
    return _get_weather(
        city, country, "/data/2.5/forecast", state, location
    )
