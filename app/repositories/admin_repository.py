from typing import Optional
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin import Admin

class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[Admin]:
        result = await self.db.execute(select(Admin).filter(Admin.email == email))
        return result.scalars().first()

    async def get_by_id(self, admin_id: int) -> Optional[Admin]:
        result = await self.db.execute(select(Admin).filter(Admin.id == admin_id))
        return result.scalars().first()

    async def get_by_reset_token(self, token: str) -> Optional[Admin]:
        result = await self.db.execute(select(Admin).filter(Admin.reset_password_token == token))
        return result.scalars().first()

    async def update_login_stats(self, admin_id: int, ip: str, device: str) -> None:
        query = (
            update(Admin)
            .where(Admin.id == admin_id)
            .values(
                last_ip_logged=ip,
                last_device_logged=device,
                failed_login_attempts=0,
                locked_until=None,
                failed_attempts_ip=None
            )
        )
        await self.db.execute(query)
        await self.db.commit()

    async def increment_failed_attempts(self, email: str) -> None:
        query = (
            update(Admin)
            .where(Admin.email == email)
            .values(failed_login_attempts=Admin.failed_login_attempts + 1)
        )
        await self.db.execute(query)
        await self.db.commit()

    async def set_reset_token(self, email: str, token: str, expires_at: datetime) -> bool:
        query = (
            update(Admin)
            .where(Admin.email == email)
            .values(reset_password_token=token, reset_password_token_expires_at=expires_at)
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0

    async def update_password(self, admin_id: int, new_hashed_password: str) -> None:
        query = (
            update(Admin)
            .where(Admin.id == admin_id)
            .values(
                hashed_password=new_hashed_password,
                reset_password_token=None,
                reset_password_token_expires_at=None
            )
        )
        await self.db.execute(query)
        await self.db.commit()

    async def update_email(self, admin_id: int, new_email: str) -> None:
        query = update(Admin).where(Admin.id == admin_id).values(email=new_email)
        await self.db.execute(query)
        await self.db.commit()

    async def lock_account(self, admin_id: int, lock_until: datetime, ip: str | None) -> None:
        query = (
            update(Admin)
            .where(Admin.id == admin_id)
            .values(locked_until=lock_until, failed_attempts_ip=ip)
        )
        await self.db.execute(query)
        await self.db.commit()

    async def reset_failed_attempts(self, admin_id: int) -> None:
        query = (
            update(Admin)
            .where(Admin.id == admin_id)
            .values(
                failed_login_attempts=0, 
                locked_until=None,
                failed_attempts_ip=None
            )
        )
        await self.db.execute(query)
        await self.db.commit()