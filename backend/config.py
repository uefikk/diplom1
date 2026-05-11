import os

APP_TITLE = "Personnel Costs Analytics 3.0"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./personnel_costs.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change_this_secret_key_for_production")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "*")
if CORS_ORIGINS_RAW.strip() == "*":
    CORS_ORIGINS = ["*"]
else:
    CORS_ORIGINS = [x.strip() for x in CORS_ORIGINS_RAW.split(",") if x.strip()]
