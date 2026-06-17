from sqlalchemy import Column, Float, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

# Rapport astrologique généré.
class AstrologicalReport(Base):
    __tablename__ = "astrological_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Données générées
    astral_data_json = Column(JSON, nullable=True)
    ai_content_json = Column(JSON, nullable=True)
    
    # Fichier PDF final
    pdf_url = Column(String(512), nullable=True)
    pdf_name = Column(String(255), nullable=True)
    
    # Monitoring performance
    generation_duration = Column(Float, nullable=False, default=0)
    error_log = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    order = relationship("Order", back_populates="report")