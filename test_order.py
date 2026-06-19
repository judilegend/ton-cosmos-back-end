import asyncio
from app.database.session import SessionLocal
from app.repositories.order_repository import OrderRepository
from app.services.astrology_service import AstrologyService
from datetime import time

async def main():
    db = SessionLocal()
    repo = OrderRepository(db)
    order = await repo.get_by_id(20)
    print("ORDER INFO:", order.id, order.birth_date, order.birth_time, order.latitude, order.longitude)
    
    # Try running the same calculation to see the exact stack trace!
    astro = AstrologyService()
    try:
        res = await astro.get_forecast_chart(
            b_date=order.birth_date,
            b_time=order.birth_time or time(12, 0),
            tz_name=order.timezone or "UTC",
            lat=order.latitude,
            lon=order.longitude
        )
        print("SUCCESS FORECAST!")
    except Exception as e:
        import traceback
        traceback.print_exc()

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
