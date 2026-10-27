import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    OPENWEATHER_BASE_URL = os.getenv(
        "OPENWEATHER_BASE_URL", "https://api.openweathermap.org"
    ).rstrip("/")
    OPENWEATHER_TIMEOUT = float(os.getenv("OPENWEATHER_TIMEOUT", "8"))
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "weatherhub_db")
    MYSQL_CHARSET = "utf8mb4"
