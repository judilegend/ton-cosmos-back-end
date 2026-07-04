import stripe
from fastapi import HTTPException
from app.core.config import settings
from typing import Optional

stripe.api_key = settings.STRIPE_SECRET_KEY

PLAN_PRICE_MAP = {
    "essentiel":         lambda: settings.STRIPE_PRICE_ID_ESSENTIAL,
    "complet":           lambda: settings.STRIPE_PRICE_ID_PREMIUM,
    "annee_cosmique":    lambda: settings.STRIPE_PRICE_ID_ANNEE_COSMIQUE,
    "cosmos_integral":   lambda: settings.STRIPE_PRICE_ID_COSMOS_INTEGRAL,
}

class StripeService:
    @staticmethod
    async def create_checkout_session(
        plan_type: str,
        amount_total: int,
        order_id: int,
        user_email: str,
        has_audio: bool = False,
        has_poster: bool = False,
    ) -> stripe.checkout.Session:

        plan_key = plan_type.lower()
        price_fn = PLAN_PRICE_MAP.get(plan_key)
        if not price_fn:
            raise HTTPException(status_code=400, detail="Type de forfait invalide")

        stripe_price_id = price_fn()
        if not stripe_price_id:
            raise HTTPException(
                status_code=400,
                detail=f"Price ID Stripe non configuré pour le forfait '{plan_key}'. Vérifiez les variables d'environnement."
            )

        # Build line items
        line_items = [{"price": stripe_price_id, "quantity": 1}]

        # Order bumps — only for plans that don't already bundle them
        is_integral = plan_key == "cosmos_integral"
        if has_audio and not is_integral:
            if not settings.STRIPE_PRICE_ID_AUDIO_BUMP:
                raise HTTPException(status_code=400, detail="Price ID Stripe pour l'audio non configuré.")
            line_items.append({"price": settings.STRIPE_PRICE_ID_AUDIO_BUMP, "quantity": 1})

        if has_poster and not is_integral:
            if not settings.STRIPE_PRICE_ID_POSTER:
                raise HTTPException(status_code=400, detail="Price ID Stripe pour le poster non configuré.")
            line_items.append({"price": settings.STRIPE_PRICE_ID_POSTER, "quantity": 1})

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                customer_email=user_email,
                metadata={
                    "plan_type": plan_key,
                    "order_id": str(order_id),
                    "stripe_price_id": stripe_price_id,
                    "has_audio": "true" if (has_audio or is_integral) else "false",
                    "has_poster": "true" if (has_poster or is_integral) else "false",
                },
                line_items=line_items,
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
    async def create_subscription_checkout_session(
        user_email: str,
        full_name: str,
        birth_date: str,
        birth_time: Optional[str],
        timezone: str,
        birth_city: str,
        latitude: float,
        longitude: float
    ) -> stripe.checkout.Session:
        if not settings.STRIPE_PRICE_ID_CERCLE_COSMOS:
            raise HTTPException(
                status_code=400,
                detail="Price ID Stripe pour l'abonnement Cercle Cosmos non configuré."
            )
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                customer_email=user_email,
                metadata={
                    "full_name": full_name,
                    "birth_date": birth_date,
                    "birth_time": birth_time or "",
                    "timezone": timezone,
                    "birth_city": birth_city,
                    "latitude": str(latitude),
                    "longitude": str(longitude),
                    "is_subscription": "true"
                },
                line_items=[{"price": settings.STRIPE_PRICE_ID_CERCLE_COSMOS, "quantity": 1}],
                success_url=f"{settings.FRONTEND_URL}/payments-success?subscription=success",
                cancel_url=f"{settings.FRONTEND_URL}/payments",
            )
            return session
        except stripe.error.StripeError as e:
            print(f"STRIPE SUBSCRIPTION ERROR: {repr(e)}")
            raise HTTPException(
                status_code=400,
                detail=getattr(e, "user_message", "Erreur lors de la transaction d'abonnement avec Stripe")
            )
        except Exception as e:
            print(f"INTERNAL STRIPE SUBSCRIPTION ERROR: {e}")
            raise HTTPException(
                status_code=500,
                detail="Une erreur interne est survenue lors de la création de la session d'abonnement"
            )

    @staticmethod
    async def create_portal_session(stripe_customer_id: str) -> stripe.billing_portal.Session:
        try:
            session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=f"{settings.FRONTEND_URL}/",
            )
            return session
        except stripe.error.StripeError as e:
            print(f"STRIPE PORTAL ERROR: {repr(e)}")
            raise HTTPException(
                status_code=400,
                detail=getattr(e, "user_message", "Erreur lors de l'accès au portail Stripe")
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

