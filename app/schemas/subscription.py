from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import date, datetime, time
from typing import Optional
from app.models.subscription import SubscriptionStatus

class SubscriptionSubscribePayload(BaseModel):
    email: EmailStr
    full_name: str
    birth_date: date
    birth_time: Optional[time] = None
    timezone: str = "UTC"
    birth_city: str
    latitude: float
    longitude: float

class SubscriptionCreate(BaseModel):
    email: EmailStr
    full_name: str
    birth_date: date
    birth_time: Optional[time] = None
    timezone: str = "UTC"
    birth_city: str
    latitude: float
    longitude: float
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    current_period_end: Optional[datetime] = None

class SubscriptionResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    status: SubscriptionStatus
    birth_date: date
    birth_time: Optional[time]
    timezone: str
    birth_city: str
    latitude: float
    longitude: float
    current_period_end: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PortalSessionRequest(BaseModel):
    email: EmailStr
