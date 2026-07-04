import enum
from sqlalchemy import Column, Integer, String, Date, Time, Enum as SqlEnum, Float, DateTime
from sqlalchemy.sql import func
from app.database.base import Base

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    full_name = Column(String(255), nullable=True)

    # Stripe linkage
    stripe_customer_id = Column(String(255), unique=True, index=True, nullable=True)
    stripe_subscription_id = Column(String(255), unique=True, index=True, nullable=True)

    # Status
    status = Column(SqlEnum(SubscriptionStatus, name="subscription_status_enum"), default=SubscriptionStatus.ACTIVE, nullable=False)

    # Birth details (needed for monthly transit recalculation)
    birth_date = Column(Date, nullable=False)
    birth_time = Column(Time, nullable=True)
    timezone = Column(String(50), nullable=False, default="UTC")
    birth_city = Column(String(250), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    current_period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
