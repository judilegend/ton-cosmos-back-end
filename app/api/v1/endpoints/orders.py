import os
import anyio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.deps import get_db
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Depends, status, Request, WebSocket, WebSocketDisconnect, HTTPException
from app.services.response_service import ServiceResponse
from app.repositories.order_repository import OrderRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.admin_repository import AdminRepository

from app.schemas.order import *
from app.schemas.report import *
from app.core.websocket_manager import manager

from app.services.utility_service import JWTService
from app.services.astrology_service import AstrologyService
from app.services.stripe_service import StripeService
from app.services.email_service import EmailService
from app.services.pdf_service import PDFService

router = APIRouter()
jwt_service = JWTService()

class TestChartPayload(BaseModel):
    birth_date: date
    birth_time: time
    timezone: str = "Europe/Paris"
    latitude: float
    longitude: float


@router.post("/test-chart")
async def test_chart(body: TestChartPayload):
    astrology_service = AstrologyService()
    chart = await astrology_service.get_full_chart(
        b_date=body.birth_date,
        b_time=body.birth_time,
        tz_name=body.timezone,
        lat=body.latitude,
        lon=body.longitude
    )
    return chart


@router.websocket("/ws/admin-order-event")
async def websocket_endpoint_for_check_new_event(websocket: WebSocket):
    socket_admin_id = "admin-order-event"
    await manager.connect(socket_admin_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(socket_admin_id, websocket)

@router.post("/create", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(body: OrderPayload, db: AsyncSession = Depends(get_db)):
    order_repo = OrderRepository(db)
    
    amount = 990 if body.plan_type == PlanType.ESSENTIEL else 1990
    
    birth_time_obj = body.birth_time
    if isinstance(birth_time_obj, str):
        birth_time_obj = datetime.strptime(birth_time_obj, "%H:%M").time()
        
    # Création asynchrone
    order_data = body.dict()
    order_data.update({
        "birth_time": birth_time_obj,
        "amount_total": amount,
        "status": OrderStatus.PENDING_PAYMENT
    })
    
    # Création asynchrone
    order = await order_repo.create(order_data)
    
    data_json = jsonable_encoder(order)
    
    # Notification via WebSocket
    await manager.send_update("admin-order-event", { "order": data_json })
    
    return ServiceResponse.success(
        status_code=201,
        message="Order created successfully.",
        data=data_json
    )


@router.get("/find-all")
async def get_orders(
    skip: int = 0, 
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    repo = OrderRepository(db)
    orders = await repo.get_all_with_filter(skip=skip, limit=limit)
    total = await repo.get_total_count(search=search, status=status)
    
    return ServiceResponse.success(data={ "items": jsonable_encoder(orders), "total": total }, message="Orders lists")


@router.get("/find-all-with-report")
async def get_orders_with_report(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db)
):
    repo = OrderRepository(db)
    orders = await repo.get_all_with_report(skip=skip, limit=limit)
    return ServiceResponse.success(data=jsonable_encoder(orders), message="Orders lists")
    

@router.get("/report/download/pdf-report/{order_id}")
async def download_report(
    order_id: int, 
    db: AsyncSession = Depends(get_db)
):
    order_repo = OrderRepository(db)
    report_repo = ReportRepository(db)

    order = await order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Commande introuvable")

    report = await report_repo.get_by_order_id(order_id)
    if not report or not report.pdf_url:
        raise HTTPException(status_code=404, detail="PDF non disponible")

    file_path = report.pdf_url
    try:
        await anyio.Path(file_path).exists()
    except Exception:
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur")

    return FileResponse(
        path=file_path,
        filename=report.pdf_name,
        media_type="application/pdf"
    )
    
    
@router.get("/stats")
async def read_dashboard_stats(
    db: AsyncSession = Depends(get_db)
):
    order_repo = OrderRepository(db)
    s = await order_repo.get_dashboard_stats()
    
    stats = [
        {
            "label": "CA Aujourd'hui",
            "value": f"{s['today_revenue']:.2f}€",
            "icon": "Euro",
            "sub": f"{s['week_revenue']:.2f}€ cette semaine",
        },
        {
            "label": "CA Global",
            "value": f"{s['month_revenue']:.2f}€",
            "icon": "TrendingUp",
            "sub": f"Total: {s['total_revenue']:.2f}€",
        },
        {
            "label": "En cours",
            "value": str(s['processing_orders']),
            "icon": "Users",
            "sub": f"{s['total_paid']} ventes totales",
        },
        {
            "label": "Taux de livraison",
            "value": f"{s['delivery_rate']}%",
            "icon": "BarChart3",
            "sub": f"{s['failed_deliveries']} erreur(s) technique(s)",
            "alert": s['delivery_rate'] < 95 and s['total_paid'] > 0,
        },
    ]

    return ServiceResponse.success(
        message="Statistiques récupérées avec succès",
        data=jsonable_encoder(stats)
    )
    

@router.delete("/delete/{order_id}")
async def delete_order(
    order_id: int, 
    db: AsyncSession = Depends(get_db)
):
    order_repo = OrderRepository(db)
    
    order = await order_repo.get_by_id(order_id)
    if not order:
        return ServiceResponse.error(status_code=404, message="Commande introuvable")
    
    try:
        success = await order_repo.delete_by_id(order_id)
        if not success:
            return ServiceResponse.error(status_code=500, message="Erreur lors de la suppression")
            
        return ServiceResponse.success(message=f"Commande {order_id} supprimée")
    except Exception as e:
        return ServiceResponse.error(status_code=500, message=f"Erreur serveur : {str(e)}")
