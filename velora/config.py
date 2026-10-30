"""Application configuration, driven by environment variables (see .env.example)."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _path(name, default):
    """Resolve a configurable path; relative paths are anchored to the project root,
    so the app never depends on the current working directory."""
    raw = os.environ.get(name) or default
    p = Path(raw)
    if not p.is_absolute():
        p = BASE_DIR / p
    return p


class Config:
    APP_NAME = "Velora Market"
    SECRET_KEY = os.environ.get("SECRET_KEY") or ""
    ENV_NAME = os.environ.get("VELORA_ENV", "development")

    DATA_DIR = _path("VELORA_DATA_DIR", "instance")
    UPLOAD_FOLDER = _path("VELORA_UPLOAD_DIR", "instance/uploads")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + str(_path("VELORA_DB_PATH", "instance/velora.db"))
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 15}}

    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "4")) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    # Sessions / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 4

    # Commerce
    BASE_CURRENCY = "PHP"
    DISPLAY_CURRENCIES = ["PHP", "USD", "EUR", "GBP", "JPY", "SGD", "AUD"]
    PRODUCTS_PER_PAGE = 12

    # Login brute-force protection
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_LOCK_MINUTES = int(os.environ.get("LOGIN_LOCK_MINUTES", "15"))

    # External APIs
    HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "8"))
    CONTACT_EMAIL = os.environ.get("VELORA_CONTACT_EMAIL", "admin@example.com")
    OFF_BASE_URL = os.environ.get("OFF_BASE_URL", "https://world.openfoodfacts.org")
    FRANKFURTER_BASE_URL = os.environ.get("FRANKFURTER_BASE_URL", "https://api.frankfurter.dev/v1")
    FX_CACHE_HOURS = float(os.environ.get("FX_CACHE_HOURS", "6"))
    API_RETRY_BACKOFF_MINUTES = float(os.environ.get("API_RETRY_BACKOFF_MINUTES", "10"))


class DevelopmentConfig(Config):
    DEBUG = False  # never expose the Werkzeug debugger by default, even in dev


class ProductionConfig(Config):
    pass


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    FX_CACHE_HOURS = 6
    API_RETRY_BACKOFF_MINUTES = 0


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
