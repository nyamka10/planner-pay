from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Payment, User
from ..security import require_admin
from ..templating import render

router = APIRouter(prefix="/admin")


@router.get("")
def admin_page(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    pending = db.query(User).filter(User.is_approved == False).order_by(User.created_at.asc()).all()  # noqa: E712
    approved = db.query(User).filter(User.is_approved == True).order_by(User.username.asc()).all()  # noqa: E712
    counts = {
        u.id: db.query(Payment).filter(Payment.user_id == u.id).count() for u in approved
    }
    return render(request, "admin.html", pending=pending, approved=approved, counts=counts)


@router.post("/users/{user_id}/approve")
def approve(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u:
        u.is_approved = True
        db.commit()
    return RedirectResponse("/admin", status_code=302)


@router.post("/users/{user_id}/reject")
def reject(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u and not u.is_admin:
        db.delete(u)
        db.commit()
    return RedirectResponse("/admin", status_code=302)
