from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import date, datetime, time
from typing import Optional, List
from app.models.order import OrderStatus, PlanType

class OrderPayload(BaseModel):
    email: EmailStr
    full_name: str
    birth_date: date
    birth_time: time
    timezone: str
    birth_city: str
    latitude: float
    longitude: float
    plan_type: PlanType
    

class PaidPayload(BaseModel):
    session_id: str
    order_id: int
    

class OrderCreate(BaseModel):
    email: EmailStr
    full_name: str
    birth_date: date
    birth_time: time
    timezone: str
    birth_city: str
    latitude: float
    longitude: float
    plan_type: PlanType
    amount_total: int
    status: str

class OrderResponse(BaseModel):
    id: int
    email: str
    status: OrderStatus
    plan_type: PlanType
    amount_total: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)