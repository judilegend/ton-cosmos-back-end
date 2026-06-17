import stripe
from fastapi import HTTPException
from app.core.config import settings
from typing import Optional


stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    @staticmethod
    async def create_checkout_session(
        plan_type: str, 
        amount_total: int, 
        order_id: int, 
        user_email: str
    ) -> stripe.checkout.Session:
        
        if plan_type.lower() == "essentiel":
            stripe_price_id = settings.STRIPE_PRICE_ID_ESSENTIAL
        elif plan_type.lower() == "complet":
            stripe_price_id = settings.STRIPE_PRICE_ID_PREMIUM
        else:
            raise HTTPException(status_code=400, detail="Type de forfait invalide")
        
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                customer_email=user_email,
                metadata={
                    "plan_type": plan_type,
                    "order_id": str(order_id),
                    "stripe_price_id": stripe_price_id
                },
                line_items=[
                    {
                        "price": stripe_price_id,
                        "quantity": 1,
                    }
                ],
                success_url=f"{settings.FRONTEND_URL}/payments-success?session_id={{CHECKOUT_SESSION_ID}}&order_id={order_id}",
                cancel_url=f"{settings.FRONTEND_URL}/payments",
            )
            return session
        
        except stripe.error.StripeError as e:
            print(f"STRIPE ERROR: {repr(e)}")
            raise HTTPException(
                status_code=400,
                detail=getattr(e, "user_message", "Erreur lors de la transaction avec Stripe")
            )
        except Exception as e:
            print(f"INTERNAL STRIPE SERVICE ERROR: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Une erreur interne est survenue lors de la création de la session de paiement"
            )

    @staticmethod
    async def verify_webhook(payload: bytes, sig_header: str) -> Optional[stripe.Event]:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            print(f"WEBHOOK ERROR: {str(e)}")
            return None
