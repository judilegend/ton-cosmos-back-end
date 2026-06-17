from datetime import datetime, timezone
from typing import Optional
from app.models.token import Token
from app.repositories.token_repository import TokenRepository

class TokenService:
    def __init__(self, repo: TokenRepository):
        self.repo = repo


    async def revoke_token(self, user_id: int, token: str, token_type: str, exp: datetime) -> Token:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        new_token = Token(
            token_hash=token,
            token_type=token_type,
            user_id=user_id,
            exp=exp
        )

        return await self.repo.create_token(new_token)


    async def find_by_token(self, token: str) -> Optional[Token]:
        return await self.repo.get_by_hash(token)


    async def is_token_revoked(self, token: str) -> bool:
        token_record = await self.repo.get_by_hash(token)
        return token_record is not None


    async def cleanup_expired_tokens(self) -> None:
        await self.repo.delete_expired_tokens()
