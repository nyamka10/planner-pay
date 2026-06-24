from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..email_utils import send_email
from ..models import User
from ..security import hash_password, require_user, verify_password
from ..templating import render

router = APIRouter(prefix="/settings")


@router.get("")
def settings_page(request: Request, user: User = Depends(require_user)):
    return render(request, "settings.html")


@router.post("/email")
def update_email(
    request: Request,
    notify_emails: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    # Убираем пустые поля и дубли, валидируем каждый адрес.
    emails, seen = [], set()
    for raw in notify_emails:
        e = raw.strip()
        if not e:
            continue
        try:
            validate_email(e, check_deliverability=False)
        except EmailNotValidError:
            return render(request, "settings.html", error=f"Некорректный адрес: {e}")
        if e.lower() not in seen:
            seen.add(e.lower())
            emails.append(e)

    if not emails:
        return render(request, "settings.html", error="Укажите хотя бы один адрес")

    user.notify_email = ", ".join(emails)
    db.commit()
    return render(request, "settings.html", info=f"Сохранено адресов: {len(emails)}")


@router.post("/password")
def update_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if not verify_password(old_password, user.password_hash):
        return render(request, "settings.html", error="Текущий пароль неверен")
    if new_password != new_password2:
        return render(request, "settings.html", error="Новые пароли не совпадают")
    if len(new_password) < 6:
        return render(request, "settings.html", error="Пароль должен быть не короче 6 символов")
    user.password_hash = hash_password(new_password)
    db.commit()
    return render(request, "settings.html", info="Пароль обновлён")


@router.post("/test-email")
def test_email(request: Request, user: User = Depends(require_user)):
    ok = send_email(
        user.recipients,
        "Тестовое письмо — проверка SMTP",
        "<p>Если вы видите это письмо — SMTP настроен корректно ✅</p>"
        f"<p>Получатели: {user.recipients_str}</p>",
    )
    if ok:
        return render(request, "settings.html", info=f"Тестовое письмо отправлено ✅ ({user.recipients_str})")
    return render(request, "settings.html", error="Не удалось отправить. Проверьте настройки SMTP в .env")
