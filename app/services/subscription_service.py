import logging
from datetime import datetime, timezone
from app.database.session import SessionLocal
from app.repositories.subscription_repository import SubscriptionRepository
from app.models.subscription import SubscriptionStatus
from app.schemas.subscription import SubscriptionCreate
from app.services.astrology_service import AstrologyService
from app.services.claude_service import AIService
from app.services.pdf_service import PDFService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

class SubscriptionService:
    @staticmethod
    async def process_checkout(session: dict):
        metadata = session.get("metadata", {})
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        stripe_customer_id = session.get("customer")
        stripe_subscription_id = session.get("subscription")

        async with SessionLocal() as db:
            sub_repo = SubscriptionRepository(db)
            existing_sub = await sub_repo.get_by_email(customer_email)
            if existing_sub:
                logger.info(f"Subscription already exists for {customer_email}")
                # We can update the stripe IDs if necessary
                if not existing_sub.stripe_customer_id:
                    existing_sub.stripe_customer_id = stripe_customer_id
                    existing_sub.stripe_subscription_id = stripe_subscription_id
                    await db.commit()
                return

            sub_data = SubscriptionCreate(
                email=customer_email,
                full_name=metadata.get("full_name", ""),
                birth_date=datetime.fromisoformat(metadata.get("birth_date")).date(),
                birth_time=datetime.fromisoformat(metadata.get("birth_time")).time() if metadata.get("birth_time") else None,
                timezone=metadata.get("timezone", "UTC"),
                birth_city=metadata.get("birth_city", ""),
                latitude=float(metadata.get("latitude", 0.0)),
                longitude=float(metadata.get("longitude", 0.0)),
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                status=SubscriptionStatus.ACTIVE
            )
            await sub_repo.create(sub_data)
            logger.info(f"Created new subscription for {customer_email}")

    @staticmethod
    async def handle_event(event_type: str, obj: dict):
        async with SessionLocal() as db:
            sub_repo = SubscriptionRepository(db)
            
            if event_type in ["customer.subscription.updated", "customer.subscription.deleted"]:
                sub_id = obj.get("id")
                status = obj.get("status")
                current_period_end = datetime.fromtimestamp(obj.get("current_period_end"), tz=timezone.utc)
                
                sub_status = SubscriptionStatus.ACTIVE
                if status == "past_due":
                    sub_status = SubscriptionStatus.PAST_DUE
                elif status == "canceled" or status == "unpaid":
                    sub_status = SubscriptionStatus.CANCELED
                    
                await sub_repo.update_status(sub_id, sub_status)
                await sub_repo.update_period_end(sub_id, current_period_end)
                logger.info(f"Updated subscription {sub_id} to status {sub_status}")

            elif event_type == "invoice.paid":
                sub_id = obj.get("subscription")
                if sub_id:
                    # Update status to active
                    await sub_repo.update_status(sub_id, SubscriptionStatus.ACTIVE)
                    # Note: we might want to trigger the monthly forecast here if it's a renewal invoice!
                    # For now, we rely on the scheduler to process active subscriptions.
                    logger.info(f"Invoice paid for subscription {sub_id}, status ACTIVE")

            elif event_type == "invoice.payment_failed":
                sub_id = obj.get("subscription")
                if sub_id:
                    await sub_repo.update_status(sub_id, SubscriptionStatus.PAST_DUE)
                    logger.info(f"Invoice payment failed for subscription {sub_id}, status PAST_DUE")
