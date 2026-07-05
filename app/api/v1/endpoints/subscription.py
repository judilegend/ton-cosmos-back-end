from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.deps import get_db
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.order_repository import OrderRepository
from app.services.stripe_service import StripeService
from app.schemas.subscription import SubscriptionSubscribePayload, SubscriptionResponse, PortalSessionRequest
from app.services.response_service import ServiceResponse

router = APIRouter()

@router.post("/subscribe-from-order/{order_id}")
async def subscribe_from_order(order_id: int, db: AsyncSession = Depends(get_db)):
    try:
        order_repo = OrderRepository(db)
        order = await order_repo.get_by_id(order_id)
        if not order:
            return ServiceResponse.error(message="Commande non trouvée", status_code=404)

        session = await StripeService.create_subscription_checkout_session(
            user_email=order.email,
            full_name=order.full_name,
            birth_date=order.birth_date.isoformat(),
            birth_time=order.birth_time.isoformat() if order.birth_time else None,
            timezone=order.timezone,
            birth_city=order.birth_city,
            latitude=order.latitude,
            longitude=order.longitude
        )
        return ServiceResponse.success(
            message="Session d'abonnement Stripe créée avec succès",
            data={"checkout_url": session.url, "session_id": session.id}
        )
    except HTTPException as he:
        return ServiceResponse.error(message=he.detail, status_code=he.status_code)
    except Exception as e:
        return ServiceResponse.error(message=f"Erreur lors de la création de l'abonnement: {str(e)}", status_code=500)

@router.post("/subscribe")
async def subscribe(body: SubscriptionSubscribePayload):
    try:
        session = await StripeService.create_subscription_checkout_session(
            user_email=body.email,
            full_name=body.full_name,
            birth_date=body.birth_date.isoformat(),
            birth_time=body.birth_time.isoformat() if body.birth_time else None,
            timezone=body.timezone,
            birth_city=body.birth_city,
            latitude=body.latitude,
            longitude=body.longitude
        )
        return ServiceResponse.success(
            message="Session d'abonnement Stripe créée avec succès",
            data={"checkout_url": session.url, "session_id": session.id}
        )
    except HTTPException as he:
        return ServiceResponse.error(message=he.detail, status_code=he.status_code)
    except Exception as e:
        return ServiceResponse.error(message=f"Erreur lors de la création de l'abonnement: {str(e)}", status_code=500)

@router.post("/create-portal-session")
async def create_portal_session(body: PortalSessionRequest, db: AsyncSession = Depends(get_db)):
    sub_repo = SubscriptionRepository(db)
    sub = await sub_repo.get_by_email(body.email)
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Abonnement ou identifiant client Stripe non trouvé pour cet email"
        )
    try:
        session = await StripeService.create_portal_session(sub.stripe_customer_id)
        return ServiceResponse.success(
            message="Session portail client Stripe créée avec succès",
            data={"portal_url": session.url}
        )
    except HTTPException as he:
        return ServiceResponse.error(message=he.detail, status_code=he.status_code)
    except Exception as e:
        return ServiceResponse.error(message=f"Erreur portail Stripe: {str(e)}", status_code=500)

@router.get("/status/{email}", response_model=None)
async def get_subscription_status(email: str, db: AsyncSession = Depends(get_db)):
    sub_repo = SubscriptionRepository(db)
    sub = await sub_repo.get_by_email(email)
    if not sub:
        return ServiceResponse.error(message="Aucun abonnement trouvé pour cet email", status_code=404)
    
    return ServiceResponse.success(
        message="Statut de l'abonnement récupéré",
        data={
            "id": sub.id,
            "email": sub.email,
            "status": sub.status,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None
        }
    )
