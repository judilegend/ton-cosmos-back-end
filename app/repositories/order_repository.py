from typing import List, Optional
from sqlalchemy import func, select, delete, or_
from datetime import datetime, time, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderCreate

class OrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
        
    async def create(self, order_data: dict) -> Order:
        try:
            if isinstance(order_data.get("birth_time"), str):
                t_str = order_data["birth_time"]
                
                parts = [int(x) for x in t_str.split(':')]
                order_data["birth_time"] = time(*parts)
                db_order = Order(**order_data)
                
            db_order = Order(**order_data) 
            self.db.add(db_order)
            await self.db.flush() 
            await self.db.commit()
            await self.db.refresh(db_order)
            return db_order
        except Exception as e:
            await self.db.rollback()
            raise e
    
    
    async def update(self, order_id: int, order_data) -> Optional[Order]:
        db_order = await self.get_by_id(order_id)
        if not db_order:
            return None

        update_data = order_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_order, key, value)

        await self.db.commit()
        await self.db.refresh(db_order)
        return db_order


    async def get_by_id(self, order_id: int) -> Optional[Order]:
        query = select(Order).filter(Order.id == order_id)
        result = await self.db.execute(query)
        return result.scalars().first()


    async def delete_by_id(self, order_id: int) -> bool:
        db_order = await self.get_by_id(order_id)
        if db_order:
            await self.db.delete(db_order)
            await self.db.commit()
            return True
        return False


    async def get_by_stripe_session(self, session_id: str) -> Optional[Order]:
        query = select(Order).filter(Order.stripe_session_id == session_id)
        result = await self.db.execute(query)
        return result.scalars().first()


    async def get_orders_by_email(self, email: str) -> List[Order]:
        query = select(Order).filter(Order.email == email)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    

    async def get_all(self, skip: int = 0, limit: int = 10000) -> List[Order]:
        query = (
            select(Order)
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def get_all_with_report(self, skip: int = 0, limit: int = 10000) -> List[Order]:
        query = (
            select(Order)
            .options(joinedload(Order.report))
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def update_status(
        self, 
        order_id: int, 
        status: OrderStatus, 
        stripe_session_id: str = None
    ) -> Optional[Order]:
        db_order = await self.get_by_id(order_id)
        
        if db_order:
            db_order.status = status
            
            if stripe_session_id:
                db_order.stripe_session_id = stripe_session_id
            
            try:
                await self.db.commit()
                await self.db.refresh(db_order)
            except Exception as e:
                await self.db.rollback()
                print(f"Error updating order {order_id}: {e}")
                raise e
                
        return db_order
    

    async def get_dashboard_stats(self):
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        paid_statuses = [OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.COMPLETED]

        async def fetch_revenue(start_date=None):
            query = select(func.sum(Order.amount_total)).filter(
                Order.status.in_(paid_statuses)
            )
            if start_date:
                query = query.filter(Order.created_at >= start_date)
            result = await self.db.execute(query)
            return result.scalar() or 0

        today_rev = await fetch_revenue(today_start)
        week_rev = await fetch_revenue(week_start)
        month_rev = await fetch_revenue(month_start)
        total_rev = await fetch_revenue()

        async def count_orders(filters):
            query = select(func.count(Order.id)).filter(*filters)
            result = await self.db.execute(query)
            return result.scalar() or 0

        total_paid_count = await count_orders([Order.status.in_(paid_statuses)])
        completed_count = await count_orders([Order.status == OrderStatus.COMPLETED])
        processing_count = await count_orders([Order.status.in_([OrderStatus.PAID, OrderStatus.PROCESSING])])
        failed_delivery_count = await count_orders([Order.status == OrderStatus.FAILED])

        denominator = total_paid_count + failed_delivery_count
        delivery_rate = round((completed_count / denominator * 100), 1) if denominator > 0 else 0

        return {
            "today_revenue": today_rev / 100,
            "week_revenue": week_rev / 100,
            "month_revenue": month_rev / 100,
            "total_revenue": total_rev / 100,
            "total_paid": total_paid_count,
            "completed_orders": completed_count,
            "processing_orders": processing_count,
            "failed_deliveries": failed_delivery_count,
            "delivery_rate": delivery_rate
        }


    def _apply_filters(self, query, search: Optional[str] = None, status: Optional[str] = None):
            if status and status != "all":
                query = query.filter(Order.status == status)
                
            if search:
                search_filter = or_(
                    Order.full_name.ilike(f"%{search}%"),
                    Order.email.ilike(f"%{search}%")
                )
                if search.isdigit():
                    search_filter = or_(search_filter, Order.id == int(search))
                    
                query = query.filter(search_filter)
                
            return query
        

    async def get_all_with_filter(self, skip: int = 0, limit: int = 100, search: Optional[str] = None, status: Optional[str] = None) -> List[Order]:
        query = select(Order)
        
        query = self._apply_filters(query, search, status)
        
        query = (
            query.order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    
    async def get_total_count(self, search: Optional[str] = None, status: Optional[str] = None) -> int:
        query = select(func.count(Order.id))
        query = self._apply_filters(query, search, status)
        
        result = await self.db.execute(query)
        return result.scalar() or 0