from app.database.session import SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
