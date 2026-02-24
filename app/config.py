"""
Load configuration from environment variables. Uses python-dotenv to read .env
so sensitive values (database URL, secrets) stay out of code and work locally
and on Railway.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Database URL. For local dev use SQLite; for production set to PostgreSQL URL
# e.g. postgresql://user:password@host:5432/dbname
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./dinesight.db")

# Optional secret for future use (e.g. signing). Not used for cookie auth yet.
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

# "production" enables secure cookies and HTTPS-only behavior
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

# Optional. If set, cookie is scoped to this domain (e.g. .railway.app).
# Leave unset to use default (current host).
COOKIE_DOMAIN: str | None = os.getenv("COOKIE_DOMAIN") or None

def is_production() -> bool:
    return ENVIRONMENT.strip().lower() == "production"
