from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import settings

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["settings"] = settings
# Делаем макрос icon() доступным во всех шаблонах без импорта.
templates.env.globals["icon"] = templates.env.get_template("_icons.html").module.icon


def render(request: Request, name: str, **context):
    context.setdefault("current_user", getattr(request.state, "user", None))
    return templates.TemplateResponse(request, name, context)
