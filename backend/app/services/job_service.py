from sqlalchemy.orm import Session
from backend.app.models.job import Job


class JobService:
    @staticmethod
    def create_job(db: Session, title: str, description: str):
        job = Job(
            title=title,
            description=description
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        return job
