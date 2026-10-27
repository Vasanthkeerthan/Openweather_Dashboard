import mysql.connector
from flask import Blueprint, jsonify, request

from database import DatabaseConfigurationError, get_db_cursor
from services.api_responses import error_response, success_response
from services.database_errors import database_error_response
from services.favorites import (
    FavoriteValidationError,
    normalize_favorite_input,
    serialize_favorite,
)


favorites_create_bp = Blueprint("favorites_create", __name__)


@favorites_create_bp.post("/api/favorites")
def create_favorite():
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
                """
                INSERT INTO favorites (city, country, nickname)
                VALUES (%s, %s, %s)
                """,
                (favorite["city"], favorite["country"], favorite["nickname"]),
            )
            favorite_id = cursor.lastrowid
            cursor.execute(
                """
                SELECT id, city, country, nickname, created_at
                FROM favorites
                WHERE id = %s
                """,
                (favorite_id,),
            )
            created = cursor.fetchone()
    except mysql.connector.IntegrityError as error:
        if error.errno == 1062:
            return error_response(
                "duplicate_favorite",
                "This city and country are already in favorites.",
                409,
            )
        return error_response(
            "database_error", "The favorite could not be saved.", 500
        )
    except (DatabaseConfigurationError, mysql.connector.Error) as error:
        return database_error_response(
            error, "The favorite could not be saved."
        )

    if created is None:
        return error_response(
            "database_error", "The favorite was saved but could not be retrieved.", 500
        )
    return success_response({"favorite": serialize_favorite(created)}, 201)
