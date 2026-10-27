import mysql.connector
from flask import Blueprint, request

from database import DatabaseConfigurationError, get_db_cursor
from services.api_responses import error_response, success_response
from services.database_errors import database_error_response
from services.favorites import (
    FavoriteValidationError,
    normalize_favorite_input,
    parse_favorite_id,
    serialize_favorite,
)


favorites_update_bp = Blueprint("favorites_update", __name__)


@favorites_update_bp.put("/api/favorites/<favorite_id>")
def update_favorite(favorite_id):
    try:
        parsed_id = parse_favorite_id(favorite_id)
    except FavoriteValidationError as error:
        return error_response(error.code, error.message, 400)

    if not request.is_json:
        return error_response(
            "invalid_json", "A JSON request body is required.", 400
        )
    payload = request.get_json(silent=True)
    if payload is None:
        return error_response("invalid_json", "The JSON request body is invalid.", 400)

    try:
        favorite = normalize_favorite_input(payload)
    except FavoriteValidationError as error:
        return error_response(error.code, error.message, 400)

    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "SELECT id FROM favorites WHERE id = %s FOR UPDATE",
                (parsed_id,),
            )
            if cursor.fetchone() is None:
                return error_response("favorite_not_found", "Favorite not found.", 404)

            cursor.execute(
                """
                UPDATE favorites
                SET city = %s, country = %s, nickname = %s
                WHERE id = %s
                """,
                (
                    favorite["city"],
                    favorite["country"],
                    favorite["nickname"],
                    parsed_id,
                ),
            )
            cursor.execute(
                """
                SELECT id, city, country, nickname, created_at
                FROM favorites
                WHERE id = %s
                """,
                (parsed_id,),
            )
            updated = cursor.fetchone()
    except mysql.connector.IntegrityError as error:
        if error.errno == 1062:
            return error_response(
                "duplicate_favorite",
                "This city and country are already in favorites.",
                409,
            )
        return error_response(
            "database_error", "The favorite could not be updated.", 500
        )
    except (DatabaseConfigurationError, mysql.connector.Error) as error:
        return database_error_response(
            error, "The favorite could not be updated."
        )

    if updated is None:
        return error_response(
            "database_error", "The favorite was updated but could not be retrieved.", 500
        )
    return success_response({"favorite": serialize_favorite(updated)})
