from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.auth.api_key_auth import get_current_user
from backend.app.billing.usage_tracker import check_and_increment_usage
from backend.app.services.job_service import JobService

router = APIRouter()


def get_service():
    return JobService(db=None)


# -------------------------
# CREATE JOB (WITH USAGE LIMITS)
# -------------------------
@router.post("/jobs")
def create_new_job(
    payload: dict,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # STEP 7 USED HERE ↓↓↓
    allowed = check_and_increment_usage(
        db=db,
        api_key=user["api_key"],
        plan=user["plan"]
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Usage limit exceeded. Upgrade plan."
        )

    service = get_service()

    job_data = payload.get("job_data") or {}

    return service.create_job(
        job_data=job_data,
        users=[user],
        preferences=user.get("preferences", {})
    )
