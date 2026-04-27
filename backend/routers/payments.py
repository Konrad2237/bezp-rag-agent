import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from config import supabase_admin
from middleware import get_current_user
from datetime import datetime, timezone

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

PRICE_IDS = {
    "week": os.getenv("STRIPE_PRICE_WEEK"),
    "month": os.getenv("STRIPE_PRICE_MONTH"),
    "quarter": os.getenv("STRIPE_PRICE_QUARTER"),
}

FRONTEND_URL = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")


class CheckoutRequest(BaseModel):
    plan: str  # "week" | "month" | "quarter"


@router.post("/payments/create-checkout-session")
async def create_checkout_session(
    body: CheckoutRequest,
    user_id: str = Depends(get_current_user),
):
    """Checkout dla zalogowanego usera — subskrypcja aktywuje się natychmiast."""
    price_id = PRICE_IDS.get(body.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Nieprawidłowy plan")

    profile = supabase_admin.table("user_profiles").select(
        "stripe_customer_id, imie, nazwisko"
    ).eq("user_id", user_id).single().execute()

    customer_id = profile.data.get("stripe_customer_id") if profile.data else None

    if not customer_id:
        auth_user = supabase_admin.auth.admin.get_user_by_id(user_id)
        email = auth_user.user.email if auth_user.user else None

        customer = stripe.Customer.create(
            email=email,
            metadata={"user_id": user_id},
        )
        customer_id = customer.id

        supabase_admin.table("user_profiles").update(
            {"stripe_customer_id": customer_id}
        ).eq("user_id", user_id).execute()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{FRONTEND_URL}/pricing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{FRONTEND_URL}/pricing",
        client_reference_id=user_id,
        metadata={"user_id": user_id},
    )

    return {"checkout_url": session.url}


@router.post("/payments/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except stripe.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Nieprawidłowy podpis webhooka")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = data.get("client_reference_id") or data.get("metadata", {}).get("user_id")
        subscription_id = data.get("subscription")

        if subscription_id and user_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            end_dt = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc).isoformat()
            customer_id = data.get("customer")

            supabase_admin.table("user_profiles").update({
                "subscription_status": "active",
                "subscription_end_date": end_dt,
                "stripe_customer_id": customer_id,
            }).eq("user_id", user_id).execute()

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        if customer_id:
            supabase_admin.table("user_profiles").update({
                "subscription_status": "cancelled",
            }).eq("stripe_customer_id", customer_id).execute()

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        if customer_id:
            supabase_admin.table("user_profiles").update({
                "subscription_status": "past_due",
            }).eq("stripe_customer_id", customer_id).execute()

    return {"status": "ok"}
