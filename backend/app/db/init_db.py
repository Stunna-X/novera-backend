# backend/app/db/init_db.py

from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.db import init_models  # ensures models are loaded


def init_db():
    Base.metadata.create_all(bind=engine)
