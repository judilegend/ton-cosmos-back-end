from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import List, Optional

from app.models.token import Token


class TokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def create_token(self, token: Token) -> Token:
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        return token
    

    async def get_by_hash(self, token_hash: str) -> Optional[Token]:
        query = select(Token).filter(Token.token_hash == token_hash)
        result = await self.db.execute(query)
        return result.scalars().first()
    

    async def get_user_tokens(self, user_id: int) -> List[Token]:
        query = select(Token).filter(Token.user_id == user_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    

    async def get_valid_tokens(self, user_id: int) -> List[Token]:
        now = datetime.now(timezone.utc)
        query = select(Token).filter(
            Token.user_id == user_id,
            Token.exp > now
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    

    async def delete_token(self, token_hash: str) -> bool:
        token = await self.get_by_hash(token_hash)

        if not token:
            return False

        await self.db.delete(token)
        await self.db.commit()
        return True
    

    async def delete_user_tokens(self, user_id: int) -> None:
        query = delete(Token).filter(Token.user_id == user_id)
        await self.db.execute(query)
        await self.db.commit()
        

    async def delete_expired_tokens(self) -> None:
        now = datetime.now(timezone.utc)
        query = delete(Token).filter(Token.exp <= now)
        await self.db.execute(query)
        await self.db.commit()
