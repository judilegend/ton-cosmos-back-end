from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from app.database.base import Base


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    token_type = Column(String(20), nullable=False)  # access / refresh
    user_id = Column(Integer, ForeignKey("admin.id"), nullable=False)
    exp = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())