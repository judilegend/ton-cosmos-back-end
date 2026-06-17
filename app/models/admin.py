from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, DateTime
from app.database.base import Base

class Admin(Base):
    __tablename__ = "admin"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    client_secret = Column(String(255), nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # Gestion mot de passe oublié
    reset_password_token = Column(String(255), nullable=True)
    reset_password_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Sécurité dashboard
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    failed_attempts_ip = Column(String(45), nullable=True)
    
    last_device_logged = Column(String(255), nullable=True)
    last_ip_logged = Column(String(45), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

