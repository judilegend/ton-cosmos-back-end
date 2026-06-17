import os
import stripe
import asyncio
import logging
from sqlalchemy import update
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
    plan_type: str  # "essentiel" | "complet"
    order_id: int
    amount_total: int
    email: str


@router.post("/create-checkout-session")
async def create_checkout(body: OrderRequest):
    try:
        session = await stripe_service.create_checkout_session(
            plan_type=body.plan_type,
            amount_total=body.amount_total,
            order_id=body.order_id,
            user_email=body.email
        )
        
        return ServiceResponse.success(
            message="Session de paiement créée",
            data={"checkout_url": session.url, "session_id": session.id}
        )
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


@router.websocket("/order/ws/order-status-for-admin")
async def websocket_endpoint_for_check_new_event(websocket: WebSocket):
    admin_socket_session = "order-status-for-admin"
    await manager.connect(admin_socket_session, websocket)
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(admin_socket_session, websocket)


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

    if event["type"] != "checkout.session.completed":
        return {"status": "ignored"}

    session_obj = event["data"]["object"]
    session = session_obj.to_dict() if hasattr(session_obj, "to_dict") else session_obj
    
    session_id = session.get("id")
    metadata = session.get("metadata", {})
    order_id = metadata.get("order_id")
    payment_status = session.get("payment_status")
    amount_paid = session.get("amount_total")

    logger.info(f"DEBUG: Session={session_id} | Order={order_id} | Status={payment_status} | Amount={amount_paid}")
    
    VALID_AMOUNTS = {990, 1990}

    if not session_id or not order_id:
        logger.warning("Missing data: session_id or order_id in metadata")
        return {"status": "error", "message": "Missing order_id in metadata"}

    if payment_status != "paid":
        logger.info(f"Paiement non finalisé. Status: {payment_status}")
        return {"status": "not_paid"}

    if amount_paid not in VALID_AMOUNTS:
        logger.warning(f"Montant incohérent pour la commande {order_id}. Reçu: {amount_paid}")
        return {"status": "invalid_amount"}

    try:
        logger.info(f"Validation commande {order_id} lancée en arrière-plan...")
        
        background_tasks.add_task(process_order_pipeline, int(order_id), session_id, False)
        
    except ValueError:
        logger.error(f"Erreur: order_id '{order_id}' n'est pas un nombre valide.")
        return {"status": "invalid_id"}
    
    return Response(content="Webhook processed", status_code=200)


@router.post("/resend-email/{order_id}")
async def resend_email(order_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    order_repo = OrderRepository(db)
    
    order = await order_repo.get_by_id(order_id)
    if not order:
        return ServiceResponse.error(message="Commande non trouvée", status_code=404)

    background_tasks.add_task(process_order_pipeline, order_id, None, True)
    
    return ServiceResponse.success(message="Le processus de génération et d'envoi a été relancé.")

    
async def process_order_pipeline(order_id: int, stripe_session_id: str | None = None, resend: bool = False):
    async with SessionLocal() as db:
        order_repo = OrderRepository(db)
        report_repo = ReportRepository(db)

        admin_ws = "order-status-for-admin"
        socket_session_id = f"ton-cosmos-{order_id}"

        try:
            order = await order_repo.get_by_id(order_id)
            if not order:
                logger.error(f"Order {order_id} not found")
                return

            # éviter double traitement Stripe
            if not resend and stripe_session_id:
                existing = await order_repo.get_by_stripe_session(stripe_session_id)
                if existing and existing.status == OrderStatus.COMPLETED:
                    return

            loop = asyncio.get_running_loop()
            start_time = loop.time()

            await order_repo.update_status(
                order_id=order.id,
                status=OrderStatus.PROCESSING,
                stripe_session_id=stripe_session_id if not resend else None
            )
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

            # CHART
            chart = report.astral_data_json

            if not chart:
                tz_name = order.timezone or "UTC"
                chart = await astrology_service.get_full_chart(
                    b_date=order.birth_date,
                    b_time=order.birth_time or time(12, 0),
                    tz_name=tz_name,
                    lat=order.latitude,
                    lon=order.longitude
                )

                await report_repo.update_astral_data_json(report.id, chart)
                await db.commit()

            await manager.send_update(socket_session_id, {"step": 2, "status": True})

            # SVG
            svg_map = await ai_service.GenerateSVGMap(chart)

            # AI CONTENT
            ai_content = report.ai_content_json

            if not ai_content:
                sections = [
                    "introduction", "piliers", "mental", "dominantes",
                    "maisons_vie_1", "maisons_vie_2",
                    "amour", "mission", "destin",
                    "conseils", "synthese"
                ]

                if order.plan_type.lower() == "complet":
                    sections[8:8] = ["ombres", "aspects_majeurs", "predictions"]

                semaphore = asyncio.Semaphore(5)

                async def fetch_section(section_id):
                    for attempt in range(15):
                        async with semaphore:
                            try:
                                print(f"Analyse IA pour = {section_id} (Essai {attempt + 1}/15)")
                                return await ai_service.generate_astrology_report(
                                    chart, order.full_name, section_id
                                )
                            except Exception as e:
                                if "429" in str(e) or "rate_limit" in str(e).lower():
                                    wait_time = 5 + (attempt * 2)
                                    print(f"Rate limit sur {section_id}. Pause de {wait_time}s...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                logger.error(f"Erreur critique section {section_id}: {e}")
                                raise e
                    raise Exception(f"Rate limit persistant sur la section {section_id} après 15 essais.")

                tasks = [fetch_section(s) for s in sections]
                results = await asyncio.gather(*tasks)

                ai_content = {"sections": results}
                await report_repo.update_ai_content_json(report.id, ai_content)
                await db.commit()

            await manager.send_update(socket_session_id, {"step": 3, "status": True})

            # PDF
            pdf_url = report.pdf_url

            if not pdf_url:
                safe_name = order.full_name.replace(" ", "-") if order.full_name else "user"
                output_filename = f"report-{order.plan_type.lower()}-{safe_name}-{datetime.now().strftime('%Y%m%d')}.pdf"

                pdf_url = await pdf_service.generate_astrological_report(
                    template_name="premium_report",
                    data={
                        "full_name": order.full_name,
                        "svg_map": svg_map,
                        "birth_chart": chart.get("birth_chart", {}),
                        "ai_content": ai_content,
                        "birth_date_info": f"{order.birth_date} {order.birth_time}",
                        "forecast": chart.get("forecast", {})
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
                to=order.email,
                subject="Ton Cosmos : Ton Rapport Astral est prêt !",
                template_name="report_ready",
                data={
                    "full_name": order.full_name,
                    "current_year": datetime.now().year
                },
                attachment_path=file_path,
                use_resend=False
            )

            if not email_result.get("success"):
                raise Exception(email_result.get("message"))

            await order_repo.update_status(order.id, OrderStatus.COMPLETED)
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

