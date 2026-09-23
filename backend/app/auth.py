"""Google OIDC (state, nonce, PKCE) and revocable, opaque session cookies."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_session
from .models import LoginSession, User

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["Account"])
COOKIE_NAME = "healthpredict_session"
SESSION_SECONDS = 60 * 60 * 24 * 7
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256", "timeout": 15},
)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(401, "Vui lòng đăng nhập để tiếp tục.")
    login = await session.get(LoginSession, digest(raw))
    if not login or login.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
    user = await session.get(User, login.user_id)
    if not user:
        raise HTTPException(401, "Tài khoản không còn khả dụng.")
    return user


def public_user(user: User) -> dict:
    return {"id": user.id, "display_name": user.display_name, "email": user.email,
            "is_demo": user.is_demo, "provider": "demo" if user.is_demo else "google",
            "onboarding_completed": user.onboarding_completed}


async def issue_session(request: Request, response, user: User, session: AsyncSession):
    previous = request.cookies.get(COOKIE_NAME)
    if previous:
        await session.execute(delete(LoginSession).where(LoginSession.token_hash == digest(previous)))
    await session.execute(delete(LoginSession).where(LoginSession.expires_at < datetime.now(timezone.utc)))
    raw = secrets.token_urlsafe(48)
    session.add(LoginSession(token_hash=digest(raw), user_id=user.id,
                             expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)))
    await session.commit()
    response.set_cookie(COOKIE_NAME, raw, max_age=SESSION_SECONDS, httponly=True,
                        secure=settings.secure_cookies, samesite="lax", path="/")
    return response


@router.get("/config")
async def auth_config():
    return {"google_enabled": settings.google_enabled, "demo_enabled": settings.demo_enabled,
            "document_ai_enabled": settings.ai_enabled,
            "ai_provider": settings.ai_provider_label}


@router.get("/google")
async def google_login(request: Request):
    if not settings.google_enabled:
        return RedirectResponse("/?auth_error=unavailable", status_code=303)
    try:
        return await oauth.google.authorize_redirect(
            request, settings.app_base_url.rstrip("/") + "/api/auth/google/callback", prompt="select_account")
    except Exception:
        request.session.clear()
        return RedirectResponse("/?auth_error=unavailable", status_code=303)


@router.get("/google/callback")
async def google_callback(request: Request, session: AsyncSession = Depends(get_session)):
    if not settings.google_enabled:
        return RedirectResponse("/?auth_error=unavailable", status_code=303)
    try:
        token = await oauth.google.authorize_access_token(request)
        claims = token.get("userinfo")
        # Authlib validates signature, issuer, audience, expiry, state and nonce.
        if not claims or not claims.get("sub") or claims.get("email_verified") is not True:
            raise ValueError("Verified Google identity required")
    except Exception:
        request.session.clear()
        return RedirectResponse("/?auth_error=signin", status_code=303)
    request.session.clear()
    sub = claims["sub"]
    user = await session.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = User(google_sub=sub, email=claims.get("email"), display_name=(claims.get("name") or "Bạn")[:100])
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:  # Concurrent first-login callbacks for one identity.
            await session.rollback()
            user = await session.scalar(select(User).where(User.google_sub == sub))
    else:
        user.email = claims.get("email") or user.email
        if not user.onboarding_completed and claims.get("name"):
            user.display_name = claims["name"][:100]
    response = RedirectResponse("/", status_code=303)
    return await issue_session(request, response, user, session)


@router.post("/demo")
async def demo_login(request: Request, session: AsyncSession = Depends(get_session)):
    if not settings.demo_enabled or not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(404)
    user = User(display_name="Khách trải nghiệm", is_demo=True)
    session.add(user)
    await session.commit()
    return await issue_session(request, JSONResponse(public_user(user)), user, session)


@router.get("/me")
async def me(user: User = Depends(current_user)):
    return public_user(user)


@router.post("/logout")
async def logout(request: Request, session: AsyncSession = Depends(get_session)):
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        await session.execute(delete(LoginSession).where(LoginSession.token_hash == digest(raw)))
        await session.commit()
    request.session.clear()
    response = JSONResponse({"status": "signed_out"})
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.secure_cookies, httponly=True, samesite="lax")
    return response
