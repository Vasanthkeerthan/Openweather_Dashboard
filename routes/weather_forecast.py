from flask import Blueprint, request

from services.api_responses import error_response, success_response
from services.openweather import WeatherServiceError, get_weather_forecast


weather_forecast_bp = Blueprint("weather_forecast", __name__)


@weather_forecast_bp.get("/api/weather/forecast")
def weather_forecast():
    city = request.args.get("city", "")
    country = request.args.get("country", "")
    state = request.args.get("state", request.args.get("region", ""))
    latitude = request.args.get("latitude")
    longitude = request.args.get("longitude")
    if not city.strip():
        return error_response(
            "missing_parameters",
            "The city query parameter is required.",
            400,
        )

    try:
        forecast = get_weather_forecast(
            city, country, state, latitude, longitude
        )
    except WeatherServiceError as error:
        return error_response(error.code, error.message, error.status_code)

    return success_response(forecast)
