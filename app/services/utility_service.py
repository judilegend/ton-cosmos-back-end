from jose import jwt
from fastapi import Request
from argon2 import PasswordHasher
from app.core.config import settings
from argon2.exceptions import VerifyMismatchError
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

ph = PasswordHasher()

class PasswordService:
    def hash_password(self, password: str) -> str:
        return ph.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        try:
            return ph.verify(hashed, plain)
        except VerifyMismatchError:
            return False


class JWTService:
    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = "HS256"


    # ACCESS TOKEN (15 min)
    def create_access_token(self, user_id: int, email: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "access",
            "exp": expire
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    
    # REFRESH TOKEN
    def create_refresh_token(self, user_id: int, email: str, secret_key: str, remember: bool = False) -> str:
        days = 7 if remember else 1
        expire = datetime.now(timezone.utc) + timedelta(days=days)

        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "refresh",
            "exp": expire
        }

        return jwt.encode(payload, secret_key, algorithm=self.algorithm)


    # NEW REFRESH TOKEN
    def create_new_refresh_token(self, user_id: int, email: str, secret_key: str, expire: datetime) -> str:
        if expire.tzinfo is None:
            expire = expire.replace(tzinfo=timezone.utc)

        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "refresh",
            "exp": int(expire.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp())
        }

        return jwt.encode(payload, secret_key, algorithm=self.algorithm)
    

    # DECODE TOKEN
    def decode_token(self, token: str, secret_key: Optional[str] = None) -> Optional[dict]:
        key = secret_key or self.secret_key
        try:
            return jwt.decode(token, key, algorithms=[self.algorithm])
        except Exception as e:
            print(f"JWT DECODE ERROR: {str(e)}")
            return None


class UtilsService:
    def get_device(self, request: Request) -> Dict[str, str]:
        ip = request.headers.get("x-forwarded-for")
        if ip:
            ip = ip.split(",")[0]
        else:
            ip = request.client.host if request.client else "unknown"

        user_agent = request.headers.get("user-agent", "unknown")
        
        return {
            "device": user_agent,
            "IP": ip
        }
