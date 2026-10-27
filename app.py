from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

from config import Config
from routes.favorites_create import favorites_create_bp
from routes.favorites_delete import favorites_delete_bp
from routes.favorites_read import favorites_read_bp
from routes.favorites_update import favorites_update_bp
from routes.weather_current import current_weather_bp
from routes.weather_forecast import weather_forecast_bp
from services.api_responses import error_response, success_response


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.register_blueprint(current_weather_bp)
    app.register_blueprint(weather_forecast_bp)
    app.register_blueprint(favorites_create_bp)
    app.register_blueprint(favorites_read_bp)
    app.register_blueprint(favorites_update_bp)
    app.register_blueprint(favorites_delete_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health_check():
        return success_response({"status": "healthy"})

    @app.errorhandler(HTTPException)
    def http_error(error):
        if error.code == 404:
            return error_response(
                "not_found", "The requested resource was not found.", 404
            )
        return error_response(
            "http_error", "The request could not be completed.", error.code
        )

    @app.errorhandler(Exception)
    def unexpected_error(_error):
        app.logger.error("Unexpected application error")
        return error_response(
            "internal_server_error",
            "An unexpected internal error occurred.",
            500,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
