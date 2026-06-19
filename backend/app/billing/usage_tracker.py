from sqlalchemy.orm import Session
from datetime import date

from backend.app.models import Usage


# -------------------------
# PLAN LIMITS
# -------------------------
PLAN_LIMITS = {
    "free": 10,
    "pro": 100
}


# -------------------------
# CHECK + INCREMENT USAGE
# -------------------------
def check_and_increment_usage(db: Session, api_key: str, plan: str):

    today = str(date.today())
    limit = PLAN_LIMITS.get(plan, 10)

    usage = db.query(Usage).filter_by(
        api_key=api_key,
        date=today
    ).first()

    # create row if not exists
    if not usage:
        usage = Usage(
            api_key=api_key,
            date=today,
            count=0
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)

    # block if limit exceeded
    if usage.count >= limit:
        return False

    # increment usage
    usage.count += 1
    db.commit()

    return True


# -------------------------
# GET USAGE (FOR ANALYTICS)
# -------------------------
def get_usage(db: Session, api_key: str):
    return db.query(Usage).filter_by(api_key=api_key).all()
