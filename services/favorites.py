from datetime import date, datetime
import re


class FavoriteValidationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_favorite_input(payload):
    if not isinstance(payload, dict):
        raise FavoriteValidationError("invalid_input", "The request body must be a JSON object.")

    city = payload.get("city")
    country = payload.get("country")
    nickname = payload.get("nickname")
    if not isinstance(city, str) or not city.strip():
        raise FavoriteValidationError("invalid_input", "A non-empty city is required.")
    if not isinstance(country, str) or not country.strip():
        raise FavoriteValidationError("invalid_input", "A non-empty country code is required.")
    if nickname is not None and not isinstance(nickname, str):
        raise FavoriteValidationError("invalid_input", "Nickname must be a string or null.")

    normalized_city = " ".join(city.split())
    normalized_country = country.strip().upper()
    normalized_nickname = None
    if nickname is not None:
        normalized_nickname = " ".join(nickname.split()) or None

    if len(normalized_city) > 120:
        raise FavoriteValidationError("invalid_input", "City must be at most 120 characters.")
    if not re.fullmatch(r"[A-Z]{2}", normalized_country):
        raise FavoriteValidationError(
            "invalid_input", "Country must be a two-letter country code."
        )
    if normalized_nickname is not None and len(normalized_nickname) > 80:
        raise FavoriteValidationError(
            "invalid_input", "Nickname must be at most 80 characters."
        )

    return {
        "city": normalized_city,
        "country": normalized_country,
        "nickname": normalized_nickname,
    }


def parse_favorite_id(favorite_id):
    if not re.fullmatch(r"[0-9]+", favorite_id) or int(favorite_id) < 1:
        raise FavoriteValidationError(
            "invalid_id", "The favorite ID must be a positive integer."
        )
    return int(favorite_id)


def serialize_favorite(row):
    favorite = dict(row)
    created_at = favorite.get("created_at")
    if isinstance(created_at, (datetime, date)):
        favorite["created_at"] = created_at.isoformat()
    return favorite
