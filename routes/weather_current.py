from flask import Blueprint, request

from services.api_responses import error_response, success_response
from services.openweather import WeatherServiceError, get_current_weather


current_weather_bp = Blueprint("current_weather", __name__)


@current_weather_bp.get("/api/weather/current")
def current_weather():
    city = request.args.get("city", "")
    country = request.args.get("country", "")
    state = request.args.get("state", request.args.get("region", ""))
    if not city.strip():
        return error_response(
            "missing_parameters",
            "The city query parameter is required.",
            400,
        )

    try:
        weather = get_current_weather(city, country, state)
    except WeatherServiceError as error:
        return error_response(error.code, error.message, error.status_code)

    return success_response(weather)
