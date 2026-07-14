import asyncio
import logging
import os
from datetime import datetime, timezone, time
from app.database.session import SessionLocal
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.astrology_service import AstrologyService
from app.services.claude_service import AIService
from app.services.pdf_service import PDFService
from app.services.email_service import EmailService
from app.core.config import settings

logger = logging.getLogger(__name__)

class SubscriptionScheduler:
    def __init__(self):
        self.is_running = False
        self.astrology_service = AstrologyService()
        self.ai_service = AIService()
        self.pdf_service = PDFService()
        self.email_service = EmailService()

    async def start(self):
        self.is_running = True
        logger.info("Subscription scheduler started")
        while self.is_running:
            now = datetime.now(timezone.utc)
            # Run on the 1st of the month at around 08:00 AM UTC
            if now.day == 1 and now.hour == 8:
                try:
                    await self.run_monthly_forecast()
                except Exception as e:
                    logger.error(f"Error running monthly forecast: {e}")
                # Sleep for 24 hours to avoid running it multiple times on the same day
                await asyncio.sleep(24 * 3600)
            else:
                # Check every hour
                await asyncio.sleep(3600)

    async def run_monthly_forecast(self):
        logger.info("Starting monthly forecast generation for all active subscribers")
        async with SessionLocal() as db:
            sub_repo = SubscriptionRepository(db)
            active_subs = await sub_repo.get_all_active()
            
            for sub in active_subs:
                try:
                    b_time = sub.birth_time if sub.birth_time else time(12, 0)
                    
                    chart_data = await self.astrology_service.get_full_chart(
                        b_date=sub.birth_date,
                        b_time=b_time,
                        tz_name=sub.timezone,
                        lat=sub.latitude,
                        lon=sub.longitude
                    )
                    
                    forecast_detailed = await self.astrology_service.get_forecast_chart(
                        b_date=sub.birth_date,
                        b_time=b_time,
                        tz_name=sub.timezone,
                        lat=sub.latitude,
                        lon=sub.longitude
                    )
                    chart_data["forecast_detailed"] = forecast_detailed

                    ai_content_section = await self.ai_service.generate_astrology_report(
                        chart_data, sub.full_name or "Abonné", "predictions_detailed"
                    )
                    
                    ai_content = {"sections": [ai_content_section]}
                    
                    svg_map = await self.ai_service.GenerateSVGMap(chart_data)
                    
                    pdf_filename = f"monthly-forecast-{sub.id}-{datetime.now().strftime('%Y%m')}.pdf"
                    
                    # Create PDF - Reusing premium_report template for simplicity
                    pdf_url = await self.pdf_service.generate_astrological_report(
                        template_name="premium_report", 
                        data={
                            "full_name": sub.full_name or "Abonné",
                            "svg_map": svg_map,
                            "birth_chart": chart_data.get("birth_chart", {}),
                            "ai_content": ai_content,
                            "birth_date_info": f"{sub.birth_date} {b_time}",
                            "birth_city": sub.birth_city,
                            "latitude": sub.latitude,
                            "longitude": sub.longitude,
                            "forecast": chart_data.get("forecast", {}),
                            "forecast_detailed": chart_data.get("forecast_detailed", {}),
                            "forecast_data": chart_data.get("forecast_detailed", {}),
                            "audio_url": None,
                            "poster_url": None
                        },
                        output_filename=pdf_filename
                    )

                    file_path = os.path.join(settings.STATIC_BASE, "reports", os.path.basename(pdf_url))
                    
                    # Send Email
                    email_result = await self.email_service.send_email(
                        to=sub.email,
                        subject="Cercle Cosmos : Vos Prévisions Mensuelles",
                        template_name="report_ready",
                        data={
                            "full_name": sub.full_name or "Abonné",
                            "current_year": datetime.now().year,
                            "audio_url": None,
                            "poster_url": None
                        },
                        attachment_path=file_path,
                        use_resend=False
                    )

                    if not email_result.get("success"):
                        raise Exception(email_result.get("message"))
                        
                    logger.info(f"Generated and sent monthly forecast for {sub.email}")
                    
                except Exception as sub_err:
                    logger.error(f"Failed to generate forecast for {sub.email}: {sub_err}")
