from fastapi import APIRouter
from backend.app.services.job_service import JobService

router = APIRouter()

@router.get("/analytics/jobs/status-count")
def job_status_count():
    service = JobService(db=None)  # replace with real db later
    jobs = service.get_all_jobs()

    summary = {
        "running": 0,
        "completed": 0,
        "failed": 0
    }

    for job in jobs:
        status = job.get("status")
        if status in summary:
            summary[status] += 1

    return summary
