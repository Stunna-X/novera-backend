from fastapi import FastAPI

from backend.app.database import Base, engine
from backend.app.models.user import User  # important: registers model
from backend.app.routes.auth import router as auth_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"status": "running"}


app.include_router(auth_router, prefix="/auth", tags=["Auth"])
