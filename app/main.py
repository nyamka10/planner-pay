import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from .models import User
from .routers import admin, auth, dashboard, payments, settings as settings_router
from .scheduler import start_scheduler
from .security import hash_password
from .templating import templates  # noqa: F401  (инициализация Jinja)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("calendar_pay")

BASE_DIR = Path(__file__).resolve().parent


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == settings.admin_username).first()
        if not admin_user:
            db.add(
                User(
                    username=settings.admin_username,
                    email=settings.admin_email,
                    notify_email=settings.admin_email,
                    password_hash=hash_password(settings.admin_password),
                    is_admin=True,
                    is_approved=True,
                )
            )
            db.commit()
            logger.info("Создан администратор: %s", settings.admin_username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


async def attach_user(request: Request, call_next):
    """Кладёт текущего пользователя в request.state для шаблонов."""
    request.state.user = None
    user_id = request.session.get("user_id")
    if user_id:
        db = SessionLocal()
        try:
            request.state.user = db.get(User, user_id)
        finally:
            db.close()
    return await call_next(request)


# Порядок важен: последний add_middleware — внешний. SessionMiddleware должен
# обернуть attach_user, чтобы request.session был доступен.
app.add_middleware(BaseHTTPMiddleware, dispatch=attach_user)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=settings.session_max_age)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Редиректы из зависимостей авторизации (302 + Location).
    if exc.status_code == 302 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], status_code=302)
    if exc.status_code == 403:
        return templates.TemplateResponse(request, "error.html", {"message": "Доступ запрещён", "code": 403}, status_code=403)
    if exc.status_code == 404:
        return templates.TemplateResponse(request, "error.html", {"message": "Страница не найдена", "code": 404}, status_code=404)
    raise exc


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(settings_router.router)
