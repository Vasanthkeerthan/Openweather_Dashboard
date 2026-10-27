import mysql.connector
from flask import Blueprint

from database import DatabaseConfigurationError, get_db_cursor
from services.api_responses import error_response, success_response
from services.database_errors import database_error_response
from services.favorites import FavoriteValidationError, parse_favorite_id, serialize_favorite


favorites_read_bp = Blueprint("favorites_read", __name__)


@favorites_read_bp.get("/api/favorites")
def get_favorites():
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, city, country, nickname, created_at
                FROM favorites
                ORDER BY created_at DESC, id DESC
                """
            )
            favorites = [serialize_favorite(row) for row in cursor.fetchall()]
    except (DatabaseConfigurationError, mysql.connector.Error) as error:
        return database_error_response(
            error, "Favorites could not be retrieved."
        )

    return success_response({"favorites": favorites})


@favorites_read_bp.get("/api/favorites/<favorite_id>")
def get_favorite(favorite_id):
    try:
        parsed_id = parse_favorite_id(favorite_id)
    except FavoriteValidationError as error:
        return error_response(error.code, error.message, 400)

    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, city, country, nickname, created_at
                FROM favorites
                WHERE id = %s
                """,
                (parsed_id,),
            )
            favorite = cursor.fetchone()
    except (DatabaseConfigurationError, mysql.connector.Error) as error:
        return database_error_response(
            error, "The favorite could not be retrieved."
        )

    if favorite is None:
        return error_response("favorite_not_found", "Favorite not found.", 404)
    return success_response({"favorite": serialize_favorite(favorite)})
