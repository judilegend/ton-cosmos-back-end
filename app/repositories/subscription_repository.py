from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.subscription import SubscriptionCreate
from datetime import datetime

class SubscriptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, sub_data: SubscriptionCreate) -> Subscription:
        try:
            db_sub = Subscription(**sub_data.model_dump())
            self.db.add(db_sub)
            await self.db.flush()
            await self.db.commit()
            await self.db.refresh(db_sub)
            return db_sub
        except Exception as e:
            await self.db.rollback()
            raise e

    async def get_by_id(self, sub_id: int) -> Optional[Subscription]:
        query = select(Subscription).filter(Subscription.id == sub_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Optional[Subscription]:
        query = select(Subscription).filter(Subscription.email == email)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_stripe_subscription_id(self, sub_id: str) -> Optional[Subscription]:
        query = select(Subscription).filter(Subscription.stripe_subscription_id == sub_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all_active(self) -> List[Subscription]:
        query = select(Subscription).filter(Subscription.status == SubscriptionStatus.ACTIVE)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_status(self, sub_id: str, status: SubscriptionStatus) -> Optional[Subscription]:
        db_sub = await self.get_by_stripe_subscription_id(sub_id)
        if db_sub:
            db_sub.status = status
            try:
                await self.db.commit()
                await self.db.refresh(db_sub)
            except Exception as e:
                await self.db.rollback()
                raise e
        return db_sub

    async def update_period_end(self, sub_id: str, current_period_end: datetime) -> Optional[Subscription]:
        db_sub = await self.get_by_stripe_subscription_id(sub_id)
        if db_sub:
            db_sub.current_period_end = current_period_end
            try:
                await self.db.commit()
                await self.db.refresh(db_sub)
            except Exception as e:
                await self.db.rollback()
                raise e
        return db_sub
