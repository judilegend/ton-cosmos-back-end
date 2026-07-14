from fastapi import APIRouter
from app.api.v1.endpoints import admin, orders, stripe, storage, subscription, geocoding

api_router = APIRouter()

api_router.include_router(admin.router, prefix="/admin", tags=["Back-Office Administration"])
api_router.include_router(orders.router, prefix="/order", tags=["Astrological Reports & Orders"])
api_router.include_router(stripe.router, prefix="/stripe", tags=["Payments & Webhooks"])
api_router.include_router(storage.router, prefix="/storage", tags=["Secure File Storage"])
api_router.include_router(subscription.router, prefix="/subscription", tags=["Cosmos Club Subscriptions"])
api_router.include_router(geocoding.router, prefix="/geocoding", tags=["Geolocation & Mapping"])