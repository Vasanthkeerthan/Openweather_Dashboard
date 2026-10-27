import mysql.connector

from database import DatabaseConfigurationError
from services.api_responses import error_response


DATABASE_UNAVAILABLE_ERRNOS = {1045, 1049, 2002, 2003, 2006, 2013, 2055}


def database_error_response(error, operation_message):
    if isinstance(error, DatabaseConfigurationError) or (
        isinstance(error, mysql.connector.Error)
        and error.errno in DATABASE_UNAVAILABLE_ERRNOS
    ):
        return error_response(
            "database_unavailable", "The database is currently unavailable.", 503
        )
    return error_response("database_error", operation_message, 500)
