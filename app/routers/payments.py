from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Payment, User
from ..reminders import renew_payment
from ..security import require_user
from ..templating import render

router = APIRouter()


def _get_owned(db: Session, user: User, payment_id: int) -> Payment:
    p = db.get(Payment, payment_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return p


@router.get("/payments")
def list_payments(
    request: Request,
    show: str = "all",
    error: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    q = db.query(Payment).filter(Payment.user_id == user.id)
    if show == "active":
        q = q.filter(Payment.is_paid == False)  # noqa: E712
    elif show == "paid":
        q = q.filter(Payment.is_paid == True)  # noqa: E712
    payments = q.order_by(Payment.due_date.asc()).all()
    errors = {"past": "Нельзя создавать оплату задним числом — выберите сегодня или будущую дату."}
    return render(
        request,
        "payments.html",
        payments=payments,
        show=show,
        today=date.today(),
        error=errors.get(error),
    )


@router.post("/payments")
def create_payment(
    request: Request,
    due_date: str = Form(...),
    service: str = Form(...),
    amount: float = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    parsed = datetime.strptime(due_date, "%Y-%m-%d").date()
    if parsed < date.today():
        return RedirectResponse("/payments?error=past", status_code=302)
    p = Payment(
        user_id=user.id,
        due_date=parsed,
        service=service.strip(),
        amount=amount,
        description=description.strip(),
    )
    db.add(p)
    db.commit()
    return RedirectResponse("/payments", status_code=302)


@router.post("/payments/{payment_id}/edit")
def edit_payment(
    payment_id: int,
    due_date: str = Form(...),
    service: str = Form(...),
    amount: float = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    p = _get_owned(db, user, payment_id)
    parsed = datetime.strptime(due_date, "%Y-%m-%d").date()
    if parsed < date.today():
        return RedirectResponse("/payments?error=past", status_code=302)
    p.due_date = parsed
    p.service = service.strip()
    p.amount = amount
    p.description = description.strip()
    db.commit()
    return RedirectResponse("/payments", status_code=302)


@router.post("/payments/{payment_id}/paid")
def mark_paid(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    p = _get_owned(db, user, payment_id)
    p.is_paid = True
    p.paid_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/payments", status_code=302)


@router.post("/payments/{payment_id}/renew")
def renew(
    payment_id: int,
    due_date: str = Form(...),
    amount: float = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Продлить: текущая запись помечается оплаченной, создаётся новая
    с выбранными датой и суммой следующего платежа."""
    p = _get_owned(db, user, payment_id)
    parsed = datetime.strptime(due_date, "%Y-%m-%d").date()
    if parsed < date.today():
        return RedirectResponse("/payments?error=past", status_code=302)
    renew_payment(db, p, new_due_date=parsed, new_amount=amount)
    return RedirectResponse("/payments", status_code=302)


@router.post("/payments/{payment_id}/delete")
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    p = _get_owned(db, user, payment_id)
    db.delete(p)
    db.commit()
    return RedirectResponse("/payments", status_code=302)
