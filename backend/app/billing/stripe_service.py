import stripe
from fastapi import HTTPException

from backend.app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(api_key: str, plan: str):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    if not settings.STRIPE_PRICE_PRO:
        raise HTTPException(status_code=500, detail="Stripe price not configured")

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
                "api_key": api_key,
                "plan": plan
            }
        )

        return session.url

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )
