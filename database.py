from contextlib import contextmanager

import mysql.connector
from flask import current_app


class DatabaseConfigurationError(Exception):
    pass


def get_mysql_config():
    config = current_app.config
    if not config.get("MYSQL_HOST") or not config.get("MYSQL_USER"):
        raise DatabaseConfigurationError("MySQL connection settings are incomplete.")
    return {
        "host": config["MYSQL_HOST"],
        "port": config["MYSQL_PORT"],
        "user": config["MYSQL_USER"],
        "password": config["MYSQL_PASSWORD"],
        "database": config["MYSQL_DATABASE"],
        "charset": config["MYSQL_CHARSET"],
    }


@contextmanager
def get_db_cursor(commit=False):
    connection = mysql.connector.connect(**get_mysql_config())
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        yield cursor
        if commit:
            connection.commit()
    except Exception:
        if connection.is_connected():
            connection.rollback()
        raise
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()
