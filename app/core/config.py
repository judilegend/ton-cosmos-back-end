import json
from typing import List, Union
from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- Infos Application ---
    app_name: str = "FastAPI Async App"
    ENV: str = "development"
    debug: bool = True
    version: str = "1.0.0"

    # --- Sécurité & Auth ---
    SESSION_SECRET: str
    JWT_SECRET_KEY: str
    CORS_ORIGINS: Union[List[str], str]
    FRONTEND_URL: str

    # --- Configuration Database (PostgreSQL) ---
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    
    # --- Admin Initial ---
    ADMIN_USERNAME: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    
    # --- Service Mail (SMTP) ---
    MAIL_HOST: str
    MAIL_PORT: int
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_FROM_NAME: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL: bool = False
    
    RESEND_API_KEY: str
    RESEND_API_FROM: str
    
    # --- Intégrations Tierces ---
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_ID_ESSENTIAL: str
    STRIPE_PRICE_ID_PREMIUM: str
    STRIPE_PRICE_ID_ANNEE_COSMIQUE: str = ""
    STRIPE_PRICE_ID_COSMOS_INTEGRAL: str = ""
    STRIPE_PRICE_ID_AUDIO_BUMP: str = ""
    STRIPE_PRICE_ID_POSTER: str = ""

    ANTHROPIC_API_KEY: str

    # --- TTS ElevenLabs ---
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"

    # --- Transit Orbs (degrés) ---
    TRANSIT_ORB_CONJUNCTION: float = 5.0
    TRANSIT_ORB_OPPOSITION: float = 5.0
    TRANSIT_ORB_SQUARE: float = 5.0
    TRANSIT_ORB_TRINE: float = 5.0
    TRANSIT_ORB_SEXTILE: float = 4.0

    # Configuration du chargement des variables d'environnement
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_json_list(cls, v):
        """
        Permet de transformer une chaîne JSON dans le .env en liste Python.
        Exemple dans .env: CORS_ORIGINS='["http://localhost:3000"]'
        """
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",")]
        return v
    
    
    @model_validator(mode="after")
    def verify_cors_in_production(self) -> "Settings":
        if self.ENV.lower() == "production":
            origins = self.CORS_ORIGINS
            
            if isinstance(origins, str) and origins == "*":
                raise ValueError("CORS_ORIGINS ne peut pas être '*' en environnement de production.")
            
            if isinstance(origins, list) and "*" in origins:
                raise ValueError("La liste CORS_ORIGINS ne peut pas contenir '*' en environnement de production.")
                
        return self
    
    # ---------------------------------------------------------
    # DATABASE_URL ASYNC (Utilise asyncpg)
    # ---------------------------------------------------------
    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

# Instance unique pour toute l'application
settings = Settings()