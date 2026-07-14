import enum
from sqlalchemy import Column, Integer, String, Date, Time, Enum as SqlEnum, Float, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

# Statut de la commande dans le pipeline.
class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    

# Type de produit acheté.
class PlanType(str, enum.Enum):
    ESSENTIEL = "essentiel"  # 9,90€
    COMPLET = "complet"    # 24,90€
    ANNEE_COSMIQUE = "annee_cosmique"  # 34,90€
    COSMOS_INTEGRAL = "cosmos_integral"  # 59,90€


# Représente une commande utilisateur.
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    
    # Données natales pour le rapport
    birth_date = Column(Date, nullable=False)
    birth_time = Column(Time, nullable=True)
    timezone = Column(String(50), nullable=False, default="UTC")
    birth_city = Column(String(250), nullable=False)
    
    # Coordonnées géographiques pour calcul astral
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Intégration Stripe
    stripe_session_id = Column(String(255), unique=True, index=True, nullable=True)
    plan_type = Column(SqlEnum(PlanType, name="plan_type_enum"), nullable=True)
    status = Column(SqlEnum(OrderStatus, name="order_status_enum"), default=OrderStatus.PENDING_PAYMENT,)
    amount_total = Column(Integer, nullable=False, default=0)
    has_audio = Column(Boolean, default=False, nullable=False)
    has_poster = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    report = relationship("AstrologicalReport", back_populates="order", uselist=False, cascade="all, delete-orphan")
    