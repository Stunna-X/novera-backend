from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from collections import Counter

from backend.app.database import SessionLocal
from backend.app.models import Job

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/analytics/top-titles")
def top_titles(db: Session = Depends(get_db)):
    jobs = db.query(Job.title).all()

    titles = [
        job.title.strip().lower()
        for job in jobs
        if job.title
    ]

    result = Counter(titles).most_common(10)

    return [
        {"title": title, "count": count}
        for title, count in result
    ]
