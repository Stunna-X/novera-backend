from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.user_service import create_user

router = APIRouter(
    prefix="/stripe",
    tags=["Stripe Webhook"]
)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        payload = await request.json()

        # Example fields (depends on Stripe event)
        email = payload.get("email")
        password = payload.get("password", "default123")

        if not email:
            raise HTTPException(status_code=400, detail="Email missing in webhook payload")

        user = create_user(db, email, password)

        return {
            "message": "webhook processed",
            "user_id": user.id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
