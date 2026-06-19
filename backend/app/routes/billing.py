from fastapi import APIRouter, HTTPException
import stripe

from backend.app.core.config import settings

router = APIRouter(
    tags=["Billing"]
)

# -------------------------
# STRIPE CONFIG
# -------------------------
stripe.api_key = settings.STRIPE_SECRET_KEY


# -------------------------
# CREATE CHECKOUT SESSION
# -------------------------
@router.post("/billing/checkout")
def checkout():

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Stripe secret key not configured"
        )

    if not settings.STRIPE_PRICE_PRO:
        raise HTTPException(
            status_code=500,
            detail="Stripe price ID not configured"
        )

    try:

        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[
                {
                    "price": settings.STRIPE_PRICE_PRO,
                    "quantity": 1,
                }
            ],
            success_url="http://localhost:3000/payment/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:3000/payment/cancel",

            metadata={
                "api_key": "demo_key_123",
                "plan": "pro"
            }
        )

        return {
            "checkout_url": session.url
        }

    except stripe.error.StripeError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# -------------------------
# PAYMENT SUCCESS
# -------------------------
@router.get("/payment/success")
def payment_success():

    return {
        "status": "success",
        "message": "Payment completed successfully"
    }


# -------------------------
# PAYMENT CANCELLED
# -------------------------
@router.get("/payment/cancel")
def payment_cancel():

    return {
        "status": "cancelled",
        "message": "Payment was cancelled"
    }
