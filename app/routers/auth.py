from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import (
    get_current_user,
    hash_password,
    login_user,
    logout_user,
    verify_password,
)
from ..templating import render

router = APIRouter()


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db):
        return RedirectResponse("/", status_code=302)
    return render(request, "login.html")


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return render(request, "login.html", error="Неверный логин или пароль")
    if not user.is_approved:
        return render(
            request,
            "login.html",
            error="Аккаунт ещё не подтверждён администратором.",
        )
    login_user(request, user)
    return RedirectResponse("/", status_code=302)


@router.get("/register")
def register_page(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db):
        return RedirectResponse("/", status_code=302)
    return render(request, "register.html")


@router.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    notify_email: str = Form(""),
    db: Session = Depends(get_db),
):
    username = username.strip()
    email = email.strip()
    notify_email = notify_email.strip()

    def err(msg):
        return render(request, "register.html", error=msg, username=username, email=email)

    if len(username) < 3:
        return err("Логин должен быть не короче 3 символов")
    if password != password2:
        return err("Пароли не совпадают")
    if len(password) < 6:
        return err("Пароль должен быть не короче 6 символов")
    try:
        validate_email(email, check_deliverability=False)
        if notify_email:
            validate_email(notify_email, check_deliverability=False)
    except EmailNotValidError:
        return err("Некорректный адрес почты")
    if db.query(User).filter(User.username == username).first():
        return err("Такой логин уже занят")

    user = User(
        username=username,
        email=email,
        notify_email=notify_email or email,
        password_hash=hash_password(password),
        is_admin=False,
        is_approved=False,
    )
    db.add(user)
    db.commit()
    return render(request, "login.html", info="Заявка отправлена. Дождитесь подтверждения администратором.")


@router.get("/pending")
def pending_page(request: Request):
    return render(request, "pending.html")


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login", status_code=302)
