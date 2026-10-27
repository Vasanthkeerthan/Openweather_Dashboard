import mysql.connector
from flask import Blueprint

from database import DatabaseConfigurationError, get_db_cursor
from services.api_responses import error_response, success_response
from services.database_errors import database_error_response
from services.favorites import FavoriteValidationError, parse_favorite_id


favorites_delete_bp = Blueprint("favorites_delete", __name__)


@favorites_delete_bp.delete("/api/favorites/<favorite_id>")
def delete_favorite(favorite_id):
    try:
        parsed_id = parse_favorite_id(favorite_id)
    except FavoriteValidationError as error:
        return error_response(error.code, error.message, 400)

    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("DELETE FROM favorites WHERE id = %s", (parsed_id,))
            deleted = cursor.rowcount > 0
    except (DatabaseConfigurationError, mysql.connector.Error) as error:
        return database_error_response(
            error, "The favorite could not be deleted."
        )

    if not deleted:
        return error_response("favorite_not_found", "Favorite not found.", 404)
    return success_response(
        {"id": parsed_id, "message": "Favorite deleted successfully."}
    )
