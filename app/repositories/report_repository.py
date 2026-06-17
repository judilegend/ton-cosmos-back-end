from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.report import AstrologicalReport
from app.schemas.report import ReportCreate

class ReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def create(self, report_data: ReportCreate) -> AstrologicalReport:
        data = report_data.model_dump()
        
        db_report = AstrologicalReport(**data)
        
        self.db.add(db_report)
        await self.db.commit()
        await self.db.refresh(db_report)
        return db_report
    

    async def get_by_order_id(self, order_id: int) -> Optional[AstrologicalReport]:
        query = select(AstrologicalReport).filter(
            AstrologicalReport.order_id == order_id
        )
        result = await self.db.execute(query)
        return result.scalars().first()
    
    
    async def get_by_id(self, report_id: int) -> Optional[AstrologicalReport]:
        query = select(AstrologicalReport).filter(AstrologicalReport.id == report_id)
        result = await self.db.execute(query)
        return result.scalars().first()
    

    async def update_content(self, report_id: int, astral_data: dict, ai_content: dict) -> Optional[AstrologicalReport]:
        db_report = await self.get_by_id(report_id)
        if db_report:
            db_report.astral_data_json = astral_data
            db_report.ai_content_json = ai_content
            await self.db.commit()
            await self.db.refresh(db_report)
        return db_report
    
    
    async def update_astral_data_json(self, report_id: int, astral_data: dict) -> Optional[AstrologicalReport]:
        db_report = await self.get_by_id(report_id)
        if db_report:
            db_report.astral_data_json = astral_data
            await self.db.commit()
            await self.db.refresh(db_report)
        return db_report


    async def update_ai_content_json(self, report_id: int, ai_content: dict) -> Optional[AstrologicalReport]:
        db_report = await self.get_by_id(report_id)
        if db_report:
            db_report.ai_content_json = ai_content
            await self.db.commit()
            await self.db.refresh(db_report)
        return db_report
    

    async def finalize_pdf(self, report_id: int, pdf_url: str, pdf_name: str, duration: int) -> Optional[AstrologicalReport]:
        db_report = await self.get_by_id(report_id)
        if db_report:
            db_report.pdf_url = pdf_url
            db_report.pdf_name = pdf_name
            db_report.generation_duration = duration
            await self.db.commit()
            await self.db.refresh(db_report)
        return db_report


    async def log_error(self, report_id: int, error_message: str) -> None:
        db_report = await self.get_by_id(report_id)
        if db_report:
            db_report.error_log = error_message
            await self.db.commit()


    async def update_asset_urls(self, report_id: int, audio_url: str = None, poster_url: str = None) -> Optional[AstrologicalReport]:
        db_report = await self.get_by_id(report_id)
        if db_report:
            if audio_url is not None:
                db_report.audio_url = audio_url
            if poster_url is not None:
                db_report.poster_url = poster_url
            await self.db.commit()
            await self.db.refresh(db_report)
        return db_report