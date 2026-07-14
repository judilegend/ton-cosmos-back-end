import os
import secrets
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter

from app.core.config import settings
from app.database.session import engine
from app.api.v1.router import api_router
from app.middleware.auth_middleware import AuthMiddleware
from app.services.subscription_scheduler import SubscriptionScheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = SubscriptionScheduler()
    scheduler_task = asyncio.create_task(scheduler.start())
    yield
    scheduler.is_running = False
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

REPORTS_DIR = os.path.join(settings.STATIC_BASE, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

app.mount(
    "/reports",
    StaticFiles(directory=REPORTS_DIR),
    name="reports"
)

# IMPORTANT: CORSMiddleware MUST be added LAST (to execute FIRST in the middleware stack)
# This ensures CORS headers are applied before other middleware processes the request
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax" if settings.ENV == "development" else "none",
    https_only=settings.ENV != "development"
)

app.add_middleware(
    AuthMiddleware,
    public_paths=[
        "/",
        "/reports",
        "/api/v1/admin/login",
        "/api/v1/admin/logout",
        "/api/v1/admin/refresh-token",
        "/api/v1/admin/reset-password",
        "/api/v1/admin/forgot-password",
        "/api/v1/admin/verify-reset-token",
        "/api/v1/stripe/create-checkout-session",
        "/api/v1/stripe/webhook",
        "/api/v1/stripe/webhooks",
        "/api/v1/order/create",
        "/api/v1/order/test-chart",
        "/api/v1/stripe/order/ws/order-status-for-admin",
        "/api/v1/stripe/ws/order-status-for-admin",
        "/api/v1/subscription/subscribe",
        "/api/v1/subscription/create-portal-session",
        "/api/v1/subscription/subscribe-from-order",
        "/api/v1/geocoding/reverse-geocode",
        "/api/v1/geocoding/geocode",
    ]
)

security = HTTPBasic()

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "status": "online",
        "message": f"Welcome to {settings.app_name} API",
        "version": settings.version
    }


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, settings.ADMIN_USERNAME)
    ok_pass = secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)

    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(get_current_username)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Docs Protégées")


@app.get("/redoc", include_in_schema=False)
async def get_redoc(username: str = Depends(get_current_username)):
    return get_redoc_html(openapi_url="/openapi.json", title="ReDoc Protégée")