import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///college_events.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = 8 * 60 * 60
    PROPAGATE_EXCEPTIONS = False


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ENGINE_OPTIONS = (
        {}
        if Config.SQLALCHEMY_DATABASE_URI.startswith("sqlite:")
        else {
            "pool_pre_ping": True,
            "pool_recycle": 280,
        }
    )
    SEND_FILE_MAX_AGE_DEFAULT = 86400
