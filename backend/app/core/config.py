import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV = os.getenv("APP_ENV", "development")

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///./jobs.db"
    )

    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO")

    API_KEY = os.getenv("API_KEY")


settings = Settings()
