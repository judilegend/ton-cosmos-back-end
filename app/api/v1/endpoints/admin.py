import secrets
import logging
from math import ceil
from fastapi.responses import JSONResponse
from jose import jwt, JWTError, ExpiredSignatureError
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, BackgroundTasks, Depends, Response, Request

from app.database.deps import get_db
from app.core.config import settings
from app.schemas.admin import LoginPayload, ForgotPayload, ResetPayload, UpdatePasswordPayload
from app.services.email_service import EmailService
from app.services.utility_service import UtilsService, PasswordService
from app.services.utility_service import JWTService
from app.services.token_service import TokenService
from app.repositories.admin_repository import AdminRepository
from app.repositories.token_repository import TokenRepository
from app.services.response_service import ServiceResponse


router = APIRouter()
logger = logging.getLogger(__name__)

service = UtilsService()
jwt_service = JWTService()
email_service = EmailService()
password_service = PasswordService()

MAX_FAILED_ATTEMPTS = 5
LOCK_TIME_MINUTES = 15

@router.post("/login")
async def login(body: LoginPayload, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    
    device = service.get_device(request=request)
    current_ip = device.get("IP") or request.client.host
    admin = await admin_repo.get_by_email(body.email)
    
    if not admin:
        return ServiceResponse.error(message="Email invalide", status_code=401, data={"error": "email"})
    
    now = datetime.now(timezone.utc)
    if admin.locked_until and admin.locked_until > now:
        remaining_time = ceil((admin.locked_until - now).total_seconds() / 60)
        return ServiceResponse.error(
            message=f"Compte bloqué. Réessaie dans {remaining_time} minute(s).", 
            status_code=423, 
            data={"error": "locked"}
        )
        
    if not password_service.verify_password(body.password, admin.hashed_password):
        await admin_repo.increment_failed_attempts(body.email)
        new_attempts = admin.failed_login_attempts + 1
        if new_attempts >= MAX_FAILED_ATTEMPTS:
            lock_target = now + timedelta(minutes=LOCK_TIME_MINUTES)
            await admin_repo.lock_account(admin.id, lock_target, current_ip)
            await db.commit()
            return ServiceResponse.error(message="Trop de tentatives. Compte bloqué.", status_code=423, data={"error": "locked"})
            
        await db.commit()
        return ServiceResponse.error(message="Mot de passe incorrect", status_code=401, data={"error": "password"})
    
    # Mise à jour des stats de login
    await admin_repo.reset_failed_attempts(admin.id)
    await admin_repo.update_login_stats(admin.id, current_ip, device.get("device"))
    await db.commit()

    access_token = jwt_service.create_access_token(
        user_id=admin.id,
        email=admin.email
    )
    
    refresh_token = jwt_service.create_refresh_token(
        user_id=admin.id, 
        email=admin.email,
        secret_key=admin.client_secret,
        remember=body.remember_me if body.remember_me else False
    )
    
    response = JSONResponse(
        content={
            "status_code": 200,
            "success": True,
            "message": "Connexion réussie",
            "data": {
                "access_token": access_token,
                "token_type": "bearer"
            }
        }
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENV == "production",
        samesite="lax" if settings.ENV == "development" else "none",
        max_age=7 * 24 * 60 * 60 if body.remember_me else 24 * 60 * 60,
        path="/"
    )
    
    return response


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)
    admin_repo = AdminRepository(db)

    def clear_cookie():
        response.delete_cookie(
            key="refresh_token",
            path="/",
            httponly=True,
            samesite="lax" if settings.ENV == "development" else "none",
        )
        
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            if payload.get("type") == "access":
                exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                await token_service.revoke_token(int(payload["sub"]), token, "access", exp)
        except Exception:
            pass
        
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, options={"verify_signature": False})
            user = await admin_repo.get_by_id(int(payload.get("sub")))
            
            if user:
                jwt.decode(refresh_token, user.client_secret, algorithms=["HS256"])
                
                exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                await token_service.revoke_token(user.id, refresh_token, "refresh", exp)
        except Exception:
            pass

    clear_cookie()

    return {
        "success": True,
        "status_code": 200,
        "message": "Logout successful"
    }


@router.post("/refresh-token")
async def refresh_token_route(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    token_repo = TokenRepository(db)
    token_service = TokenService(token_repo)
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ServiceResponse.error("Refresh token missing", 401)

    try:
        payload = jwt.decode(refresh_token, key=None, options={"verify_signature": False})
        user = await admin_repo.get_by_id(int(payload.get("sub")))
        if not user:
            return ServiceResponse.error("User not found", 404)
        
        jwt.decode(refresh_token, user.client_secret, algorithms=["HS256"])
        
        if await token_service.is_token_revoked(refresh_token):
            response.delete_cookie("refresh_token", path="/")
            return ServiceResponse.error("Session revoked", 401)

    except (JWTError, ExpiredSignatureError):
        return ServiceResponse.error("Invalid or expired session", 401)
    
    new_access = jwt_service.create_access_token(user_id=user.id, email=user.email)
    
    exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    new_refresh = jwt_service.create_new_refresh_token(
        user_id=user.id,
        email=user.email,
        secret_key=user.client_secret,
        expire=exp_dt
    )
    
    await token_service.revoke_token(user.id, refresh_token, "refresh", exp_dt)
    
    max_age = int((exp_dt - datetime.now(timezone.utc)).total_seconds())
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.ENV == "production",
        samesite="none" if settings.ENV == "production" else "lax",
        max_age=max_age,
        path="/"
    )
    
    return {
        "success": True,
        "message": "Token refreshed",
        "data": {
            "access_token": new_access,
            "token_type": "bearer"
        }
    }


@router.post("/forgot-password")
async def forgot_password(body: ForgotPayload, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    admin = await admin_repo.get_by_email(body.email)
    
    msg = "Si un compte avec cet email existe, un lien de réinitialisation a été envoyé."
    
    if not admin:
        return ServiceResponse.success(message=msg)
    
    fp_token = secrets.token_urlsafe(32)
    fp_expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    await admin_repo.set_reset_token(email=body.email, token=fp_token, expires_at=fp_expire)

    reset_link = f"{settings.FRONTEND_URL}/administrator/reset-password?token={fp_token}"
    
    background_tasks.add_task(
        email_service.send_email,
        to=admin.email,
        subject="Réinitialisation de votre mot de passe",
        template_name="reset_password",
        data={
            "full_name": "Système JVN Lab - Ton Cosmos",
            "reset_link": reset_link,
            "current_year": datetime.now().year
        }
    )
    
    return ServiceResponse.success(message=msg)


@router.get("/verify-reset-token")
async def verify_reset_token(token: str, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    admin = await admin_repo.get_by_reset_token(token)
    
    if not admin:
        return ServiceResponse.error(
            message="Ce lien de réinitialisation est invalide ou a déjà été utilisé.",
            status_code=404
        )
    
    if admin.reset_password_token_expires_at < datetime.now(timezone.utc):
        return ServiceResponse.error(
            message="Ce lien a expiré. Merci de renouveler votre demande.",
            status_code=400
        )
    
    return ServiceResponse.success("Jeton valide.")


@router.put("/reset-password")
async def reset_password_finish(body: ResetPayload, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    admin = await admin_repo.get_by_reset_token(body.token)
    
    if not admin:
        return ServiceResponse.error(
            message="Ce lien de réinitialisation est invalide ou a déjà été utilisé.",
            status_code=400
        )
    
    if admin.reset_password_token_expires_at < datetime.now(timezone.utc):
        return ServiceResponse.error(
            message="Ce lien a expiré. Merci de renouveler votre demande.",
            status_code=400
        )
    
    new_hashed = password_service.hash_password(body.new_password)
    await admin_repo.update_password(admin_id=admin.id, new_hashed_password=new_hashed)
    
    return ServiceResponse.success("Mot de passe mis à jour.")


@router.patch("/update-password")
async def update_password(body: UpdatePasswordPayload, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    user_id = request.state.user_id
    
    admin = await admin_repo.get_by_id(user_id)

    if not admin:
        return ServiceResponse.error("Utilisateur non trouvé", 404)
    
    if not password_service.verify_password(body.old_password, admin.hashed_password):
        return ServiceResponse.error("Ancien mot de passe incorrect.", 401)
    
    new_hashed = password_service.hash_password(body.new_password)
    await admin_repo.update_password(admin_id=admin.id, new_hashed_password=new_hashed)
    
    return ServiceResponse.success("Mot de passe mis à jour avec succès.")


@router.get("/data")
async def get_admin_data(request: Request, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    user_id = request.state.user_id
    admin = await admin_repo.get_by_id(user_id)
    if not admin:
        return ServiceResponse.error("Admin non trouvé", 404)
    
    return ServiceResponse.success(
        message="Données sensibles accessibles uniquement aux admins authentifiés.", 
        data={
            "email": admin.email,
            "last_device_logged": admin.last_device_logged,
            "last_ip_logged": admin.last_ip_logged,
            "updated_at": admin.updated_at
        }
    )
    
    
@router.put("/update-data")
async def update_admin_email(body: ForgotPayload, request: Request, db: AsyncSession = Depends(get_db)):
    admin_repo = AdminRepository(db)
    user_id = request.state.user_id
    admin = await admin_repo.get_by_id(user_id)
    if not admin:
        return ServiceResponse.error("Admin non trouvé", 404)
    
    await admin_repo.update_email(admin_id=admin.id, new_email=body.email)
    
    return ServiceResponse.success(
        message="Email mis à jour pour l'admin connecté.",
        data={"new_email": body.email}
    )
    