import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

def _get_clean_env(key, default=None):
    val = os.environ.get(key, default)
    if val is not None:
        return val.strip("'\"")
    return val

is_debug = _get_clean_env("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
is_testing = _get_clean_env("TESTING", "False").lower() in ("true", "1", "yes")
is_production = not (is_debug or is_testing)

SECRET_KEY = _get_clean_env("SECRET_KEY")
if not SECRET_KEY:
    if is_debug or is_testing:
        SECRET_KEY = "dev_secret_key_placeholder_local_only"
    else:
        raise RuntimeError("SECRET_KEY environment variable is required in production!")

DATABASE_URL = _get_clean_env("DATABASE_URL")
if not DATABASE_URL:
    if is_debug or is_testing:
        SQLALCHEMY_DATABASE_URI = "sqlite:///water_clogging.db"
    else:
        raise RuntimeError("DATABASE_URL environment variable is required in production!")
else:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL

SQLALCHEMY_TRACK_MODIFICATIONS = False

if SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    }

MAX_CONTENT_LENGTH = 5 * 1024 * 1024

MAIL_SERVER = _get_clean_env("MAIL_SERVER", "smtp.gmail.com")

mail_port_raw = _get_clean_env("MAIL_PORT", "587")
MAIL_PORT = int(mail_port_raw) if mail_port_raw and mail_port_raw.isdigit() else 587

mail_use_tls_raw = _get_clean_env("MAIL_USE_TLS", "True")
MAIL_USE_TLS = mail_use_tls_raw.lower() in ("true", "1", "yes")

mail_use_ssl_raw = _get_clean_env("MAIL_USE_SSL", "False")
MAIL_USE_SSL = mail_use_ssl_raw.lower() in ("true", "1", "yes")

MAIL_USERNAME = _get_clean_env("MAIL_USERNAME")
MAIL_PASSWORD = _get_clean_env("MAIL_PASSWORD")
MAIL_DEFAULT_SENDER = _get_clean_env("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

SESSION_COOKIE_SECURE = _get_clean_env(
    "SESSION_COOKIE_SECURE", "True" if is_production else "False"
).lower() in ("true", "1", "yes")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

REMEMBER_COOKIE_SECURE = _get_clean_env(
    "REMEMBER_COOKIE_SECURE", "True" if is_production else "False"
).lower() in ("true", "1", "yes")
REMEMBER_COOKIE_HTTPONLY = True
REMEMBER_COOKIE_SAMESITE = "Lax"
REMEMBER_COOKIE_DURATION = timedelta(days=14)

gov_authority_raw = _get_clean_env("GOVERNMENT_AUTHORITY_EMAIL")
if not gov_authority_raw:
    if is_production:
        raise RuntimeError("GOVERNMENT_AUTHORITY_EMAIL environment variable is required")
    else:
        GOVERNMENT_AUTHORITY_EMAIL = "authority@example.com"
else:
    GOVERNMENT_AUTHORITY_EMAIL = gov_authority_raw.strip().lower()

RATELIMIT_STORAGE_URL = _get_clean_env("RATELIMIT_STORAGE_URL")