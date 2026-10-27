from app import create_app
from config import Config


class TestConfig(Config):
    TESTING = True


def test_dashboard_renders_and_serves_static_assets():
    client = create_app(TestConfig).test_client()

    page = client.get("/")
    stylesheet = client.get("/static/css/style.css")
    script = client.get("/static/js/app.js")
    hero = client.get("/static/images/weatherhub-reference-hero.png")
    sidebar_art = client.get("/static/images/weatherhub-reference-sidebar.png")
    city_thumbnails = [
        client.get(f"/static/images/reference-{city}.png")
        for city in ("new-york", "london", "tokyo", "sydney")
    ]

    assert page.status_code == 200
    assert b"WeatherHub" in page.data
    assert b"weatherhub-reference-sidebar.png" in page.data
    assert b"/static/css/style.css" in page.data
    assert b"/static/js/app.js" in page.data
    assert stylesheet.status_code == 200
    assert b".app-shell" in stylesheet.data
    assert b"weatherhub-reference-hero.png" in stylesheet.data
    assert script.status_code == 200
    assert b"/api/weather/current" in script.data
    assert hero.status_code == 200
    assert hero.mimetype == "image/png"
    assert sidebar_art.status_code == 200
    assert sidebar_art.mimetype == "image/png"
    assert all(image.status_code == 200 and image.mimetype == "image/png" for image in city_thumbnails)


def test_dashboard_does_not_change_existing_api_routes():
    app = create_app(TestConfig)
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert {
        "/api/health",
        "/api/weather/current",
        "/api/weather/forecast",
        "/api/favorites",
        "/api/favorites/<favorite_id>",
    }.issubset(rules)
