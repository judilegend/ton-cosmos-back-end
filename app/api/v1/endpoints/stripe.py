import os
import stripe
import asyncio
import logging
from sqlalchemy import update, select
from datetime import datetime, time, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from concurrent.futures import ProcessPoolExecutor
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request, Response
from pydantic import BaseModel

from app.models.order import Order
from app.database.deps import get_db
from app.database.session import SessionLocal
from app.core.config import settings
from app.core.websocket_manager import manager
from app.services.pdf_service import PDFService
from app.services.stripe_service import StripeService
from app.services.astrology_service import AstrologyService
from app.services.email_service import EmailService
from app.services.claude_service import AIService
from app.services.response_service import ServiceResponse
from app.repositories.order_repository import OrderRepository
from app.repositories.report_repository import ReportRepository
from app.schemas.order import OrderStatus
from app.schemas.report import ReportCreate

router = APIRouter()
logger = logging.getLogger(__name__)

# Configuration Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
stripe.api_version = "2026-04-22.dahlia"

# Initialisation des services
ai_service = AIService()
pdf_service = PDFService()
email_service = EmailService()
stripe_service = StripeService()
astrology_service = AstrologyService()


class OrderRequest(BaseModel):
    plan_type: str
    order_id: int
    amount_total: int
    email: str
    has_audio: bool = False
    has_poster: bool = False


@router.post("/create-checkout-session")
async def create_checkout(body: OrderRequest):
    try:
        session = await stripe_service.create_checkout_session(
            plan_type=body.plan_type,
            amount_total=body.amount_total,
            order_id=body.order_id,
            user_email=body.email,
            has_audio=body.has_audio,
            has_poster=body.has_poster
        )
        
        return ServiceResponse.success(
            message="Session de paiement créée",
            data={"checkout_url": session.url, "session_id": session.id}
        )
    except HTTPException as he:
        logger.error(f"HTTPException Stripe Session: {he.detail}")
        return ServiceResponse.error(message=he.detail, status_code=he.status_code)
    except Exception as e:
        logger.error(f"Erreur Stripe Session: {e}")
        return ServiceResponse.error(message="Erreur lors de la création du paiement", status_code=500)


@router.websocket("/ws/{session_id}")
async def websocket_endpoint_for_check_steps(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)


@router.websocket("/ws/order-status-for-admin")
async def admin_order_status_ws(websocket: WebSocket):
    await manager.connect("admin-order-status", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("admin-order-status", websocket)


@router.websocket("/order/ws/order-status-for-admin")
async def admin_order_status_ws_secondary(websocket: WebSocket):
    await manager.connect("admin-order-status", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("admin-order-status", websocket)


@router.post("/webhook")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            endpoint_secret
        )
    except Exception as e:
        logger.error(f"Signature verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    
    if event_type not in [
        "checkout.session.completed", 
        "customer.subscription.updated", 
        "customer.subscription.deleted", 
        "invoice.paid", 
        "invoice.payment_failed"
    ]:
        return {"status": "ignored"}

    session_obj = event["data"]["object"]
    session = session_obj.to_dict() if hasattr(session_obj, "to_dict") else session_obj
    
    from app.services.subscription_service import SubscriptionService

    if event_type == "checkout.session.completed":
        metadata = session.get("metadata", {})
        if metadata.get("is_subscription") == "true":
            background_tasks.add_task(SubscriptionService.process_checkout, session)
            return Response(content="Subscription checkout processed", status_code=200)

        session_id = session.get("id")
        order_id = metadata.get("order_id")
        payment_status = session.get("payment_status")
        amount_paid = session.get("amount_total")
        
        has_audio = metadata.get("has_audio") == "true" or metadata.get("has_audio") is True
        has_poster = metadata.get("has_poster") == "true" or metadata.get("has_poster") is True

        logger.info(f"DEBUG: Session={session_id} | Order={order_id} | Status={payment_status} | Amount={amount_paid} | Audio={has_audio} | Poster={has_poster}")

        if not session_id or not order_id:
            logger.warning("Missing data: session_id or order_id in metadata")
            return {"status": "error", "message": "Missing order_id in metadata"}

        if payment_status != "paid":
            logger.info(f"Paiement non finalisé. Status: {payment_status}")
            return {"status": "not_paid"}

        try:
            logger.info(f"Validation commande {order_id} lancée en arrière-plan...")
            background_tasks.add_task(process_order_pipeline, int(order_id), session_id, False, has_audio, has_poster,amount_paid)
        except ValueError:
            logger.error(f"Erreur: order_id '{order_id}' n'est pas un nombre valide.")
            return {"status": "invalid_id"}
        
        return Response(content="Webhook processed", status_code=200)

    elif event_type in ["customer.subscription.updated", "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed"]:
        background_tasks.add_task(SubscriptionService.handle_event, event_type, session)
        return Response(content="Subscription event processed", status_code=200)

    return {"status": "ignored"}


@router.post("/resend-email/{order_id}")
async def resend_email(order_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    order_repo = OrderRepository(db)
    
    order = await order_repo.get_by_id(order_id)
    if not order:
        return ServiceResponse.error(message="Commande non trouvée", status_code=404)

    background_tasks.add_task(process_order_pipeline, order_id, None, True)
    return ServiceResponse.success(message="Le processus de génération et d'envoi a été relancé.")

    
async def process_order_pipeline(
    order_id: int,
    stripe_session_id: str | None = None,
    resend: bool = False,
    has_audio: bool = False,
    has_poster: bool = False,
    amount_total: int | None = None  
):
    admin_ws = "admin-order-status"
    socket_session_id = f"ton-cosmos-{order_id}"

    async with SessionLocal() as db:
        order_repo = OrderRepository(db)
        report_repo = ReportRepository(db)

        try:
            # Verrouiller la commande en base de données pour éviter tout traitement concurrent
            query = select(Order).filter(Order.id == order_id).with_for_update()
            result = await db.execute(query)
            order = result.scalars().first()
            
            if not order:
                logger.error(f"Order {order_id} not found")
                return

            # Vérifier l'état pour l'idempotence
            if not resend and order.status in (OrderStatus.PROCESSING, OrderStatus.COMPLETED):
                logger.info(f"Order {order_id} is already being processed or is completed. Skipping.")
                return

            # Update flags
            if not resend:
                order.has_audio = has_audio
                order.has_poster = has_poster
                if amount_total is not None:
                    order.amount_total = amount_total
            else:
                has_audio = order.has_audio
                has_poster = order.has_poster

            loop = asyncio.get_running_loop()
            start_time = loop.time()

            # Mettre à jour le statut immédiatement en PROCESSING sous le même verrou
            order.status = OrderStatus.PROCESSING
            if not resend and stripe_session_id:
                order.stripe_session_id = stripe_session_id
            
            await db.commit()
            await db.refresh(order)

            await manager.send_update(admin_ws, {"order_id": order_id, "status": OrderStatus.PROCESSING})
            await manager.send_update(socket_session_id, {"step": 1, "status": True})

            # REPORT
            report = await report_repo.get_by_order_id(order_id)
            if not report:
                report = await report_repo.create(
                    ReportCreate(order_id=order.id, generation_duration=0)
                )
                await db.commit()

            # Extraction safe des données nécessaires avant les appels asynchrones longs
            chart = report.astral_data_json or {}
            plan_type_str = str(order.plan_type.value if hasattr(order.plan_type, "value") else order.plan_type or "essentiel").lower()
            order_email = order.email
            order_full_name = order.full_name
            order_birth_date = order.birth_date
            order_birth_time = order.birth_time
            order_timezone = order.timezone
            order_latitude = order.latitude
            order_longitude = order.longitude
            order_birth_city = order.birth_city

            if not chart:
                tz_name = order_timezone or "UTC"
                chart = await astrology_service.get_full_chart(
                    b_date=order_birth_date,
                    b_time=order_birth_time or time(12, 0),
                    tz_name=tz_name,
                    lat=order_latitude,
                    lon=order_longitude
                )

            if "forecast_detailed" not in chart and plan_type_str in ("annee_cosmique", "cosmos_integral"):
                tz_name = order_timezone or "UTC"
                forecast_detailed = await astrology_service.get_forecast_chart(
                    b_date=order_birth_date,
                    b_time=order_birth_time or time(12, 0),
                    tz_name=tz_name,
                    lat=order_latitude,
                    lon=order_longitude
                )
                chart["forecast_detailed"] = forecast_detailed
                await report_repo.update_astral_data_json(report.id, chart)
                await db.commit()

            await manager.send_update(socket_session_id, {"step": 2, "status": True})

            # SVG
            svg_map = await ai_service.GenerateSVGMap(chart)

            # AI CONTENT
            ai_content = report.ai_content_json

            if not ai_content:
                if plan_type_str == "essentiel":
                    sections = ["introduction", "piliers", "mental", "dominantes", "maisons_vie_1", "maisons_vie_2", "amour", "mission", "destin", "conseils", "synthese"]
                elif plan_type_str == "complet":
                    sections = ["introduction", "piliers", "mental", "dominantes", "maisons_vie_1", "maisons_vie_2", "amour", "mission", "ombres", "aspects_majeurs", "predictions", "destin", "conseils", "synthese"]
                elif plan_type_str == "annee_cosmique":
                    sections = ["introduction", "piliers", "mental", "dominantes", "maisons_vie_1", "maisons_vie_2", "amour", "mission", "predictions_detailed", "destin", "conseils", "synthese"]
                elif plan_type_str == "cosmos_integral":
                    sections = ["introduction", "piliers", "mental", "dominantes", "maisons_vie_1", "maisons_vie_2", "amour", "mission", "ombres", "aspects_majeurs", "predictions_detailed", "karma", "destin", "conseils", "synthese"]
                else:
                    sections = ["introduction", "piliers", "mental", "dominantes", "maisons_vie_1", "maisons_vie_2", "amour", "mission", "destin", "conseils", "synthese"]

                semaphore = asyncio.Semaphore(3)  # Descendu à 3 pour éviter les surcharges de rate-limit concurrents

                async def fetch_section(section_id):
                    for attempt in range(15):
                        async with semaphore:
                            try:
                                print(f"Analyse IA pour = {section_id} (Essai {attempt + 1}/15)")
                                return await ai_service.generate_astrology_report(
                                    chart, order_full_name, section_id
                                )
                            except Exception as e:
                                if "429" in str(e) or "rate_limit" in str(e).lower():
                                    wait_time = 5 + (attempt * 2)
                                    print(f"Rate limit sur {section_id}. Pause de {wait_time}s...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                logger.error(f"Erreur section {section_id}: {e}")
                                raise e
                    raise Exception(f"Rate limit persistant sur la section {section_id} après 15 essais.")

                tasks = [fetch_section(s) for s in sections]
                results = await asyncio.gather(*tasks)

                ai_content = {"sections": results}
                await report_repo.update_ai_content_json(report.id, ai_content)
                await db.commit()

            await manager.send_update(socket_session_id, {"step": 3, "status": True})

            # SECURE AUDIO GENERATION
            if has_audio and not report.audio_url:
                await manager.send_update(socket_session_id, {"step": 4, "status": "generating_audio"})
                try:
                    from app.services.tts_service import TTSService
                    tts = TTSService()
                    tts_text_parts = []
                    for s in ai_content.get("sections", []):
                        for block in s.get("blocks", []):
                            for p in block.get("paragraphs", []):
                                if p:
                                    tts_text_parts.append(p)
                    text_for_tts = " ".join(tts_text_parts)[:4500]
                    audio_filename = f"audio-{order_id}.mp3"
                    audio_url = await tts.generate_speech(text_for_tts, audio_filename)
                    report = await report_repo.update_asset_urls(report.id, audio_url=audio_url)
                    await db.commit()
                except Exception as audio_err:
                    logger.error(f"Erreur lors de la génération de l'audio TTS : {audio_err}")

            # SECURE HD POSTER GENERATION
            if has_poster and not report.poster_url:
                await manager.send_update(socket_session_id, {"step": 4, "status": "generating_poster"})
                try:
                    from app.services.storage_service import StorageService
                    storage = StorageService()
                    safe_name = order_full_name.replace(" ", "-") if order_full_name else "user"
                    poster_filename = f"poster-{safe_name}-{order_id}.pdf"
                    
                    await pdf_service.generate_astrological_report(
                        template_name="hd_poster",
                        data={
                            "full_name": order_full_name,
                            "svg_map": svg_map,
                            "birth_date_info": f"{order_birth_date} {order_birth_time or '12:00'}",
                            "birth_city": order_birth_city,
                            "latitude": order_latitude,
                            "longitude": order_longitude
                        },
                        output_filename=poster_filename
                    )
                    
                    pdf_source_path = f"/app/static/reports/{poster_filename}"
                    storage.save_file(pdf_source_path, poster_filename)
                    signed_poster = storage.generate_signed_url(poster_filename)
                    report = await report_repo.update_asset_urls(report.id, poster_url=signed_poster)
                    await db.commit()
                except Exception as poster_err:
                    logger.error(f"Erreur lors de la génération du poster HD : {poster_err}")

            # PDF MAIN REPORT
            pdf_url = report.pdf_url

            if not pdf_url:
                safe_name = order_full_name.replace(" ", "-") if order_full_name else "user"
                output_filename = f"report-{plan_type_str}-{safe_name}-{datetime.now().strftime('%Y%m%d')}.pdf"

                if plan_type_str == "annee_cosmique":
                    template_name = "annee_cosmique"
                elif plan_type_str == "cosmos_integral":
                    template_name = "cosmos_integral"
                else:
                    template_name = "premium_report"

                pdf_url = await pdf_service.generate_astrological_report(
                    template_name=template_name,
                    data={
                        "full_name": order_full_name,
                        "svg_map": svg_map,
                        "birth_chart": chart.get("birth_chart", {}),
                        "ai_content": ai_content,
                        "birth_date_info": f"{order_birth_date} {order_birth_time or '12:00'}",
                        "birth_city": order_birth_city,
                        "latitude": order_latitude,
                        "longitude": order_longitude,
                        "forecast": chart.get("forecast", {}),
                        "forecast_detailed": chart.get("forecast_detailed", {}),
                        "forecast_data": chart.get("forecast_detailed", {}),
                        "audio_url": report.audio_url,
                        "poster_url": report.poster_url
                    },
                    output_filename=output_filename
                )

                duration = round(loop.time() - start_time, 2)
                await report_repo.finalize_pdf(report.id, pdf_url, output_filename, duration)
                await db.commit()

            await manager.send_update(socket_session_id, {"step": 4, "status": True})

            # EMAIL
            file_path = pdf_url.replace("/reports/", "/app/static/reports/")

            email_result = await email_service.send_email(
                to=order_email,
                subject="Ton Cosmos : Ton Rapport Astral est prêt !",
                template_name="report_ready",
                data={
                    "full_name": order_full_name,
                    "current_year": datetime.now().year,
                    "audio_url": report.audio_url,
                    "poster_url": report.poster_url
                },
                attachment_path=file_path,
                use_resend=False
            )

            if not email_result.get("success"):
                raise Exception(email_result.get("message"))

            await order_repo.update_status(order_id, OrderStatus.COMPLETED)
            await manager.send_update(socket_session_id, {"step": 5, "status": True})
            await manager.send_update(admin_ws, {"order_id": order_id, "status": OrderStatus.COMPLETED})
            await db.commit()

        except Exception as e:
            logger.error(f"Échec critique du traitement de la commande {order_id}: {str(e)}")
            
            try:
                await db.rollback()
            except Exception:
                pass
                
            try:
                query = update(Order).where(Order.id == order_id).values(status=OrderStatus.FAILED)
                await db.execute(query)
                await db.commit()
            except Exception as db_err:
                logger.error(f"Impossible de passer le statut à FAILED en BDD: {db_err}")

            try:
                await manager.send_update(socket_session_id, { "step": 1, "status": False, "error": str(e) })
                await manager.send_update(admin_ws, { "order_id": order_id, "status": OrderStatus.FAILED })
            except Exception as ws_err:
                logger.error(f"Échec envoi WS erreur: {ws_err}")