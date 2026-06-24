from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..email_utils import digest_email_html, send_email
from ..models import Payment, User
from ..security import require_user
from ..templating import render

router = APIRouter()

MONTHS_RU = [
    "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
    "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек",
]
MONTHS_RU_FULL = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def _level(total: float, max_total: float) -> int:
    if total <= 0:
        return 0
    if max_total <= 0:
        return 1
    ratio = total / max_total
    if ratio <= 0.25:
        return 1
    if ratio <= 0.5:
        return 2
    if ratio <= 0.75:
        return 3
    return 4


@router.get("/")
def dashboard(
    request: Request,
    year: int | None = None,
    digest: str | None = None,
    n: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    today = date.today()
    year = year or today.year

    # Сообщение после ручной отправки письма.
    digest_msg = digest_err = None
    if digest == "sent":
        digest_msg = f"Письмо отправлено на {user.recipients_str} (оплат: {n})"
    elif digest == "empty":
        digest_err = "За выбранный период предстоящих оплат нет — письмо не отправлено"
    elif digest == "fail":
        digest_err = "Не удалось отправить письмо. Проверьте SMTP в настройках"

    start = date(year, 1, 1)
    end = date(year, 12, 31)

    payments = (
        db.query(Payment)
        .filter(Payment.user_id == user.id, Payment.due_date >= start, Payment.due_date <= end)
        .all()
    )

    # Агрегация по дням.
    by_day: dict[date, dict] = {}
    monthly = [{"total": 0.0, "paid": 0.0, "upcoming": 0.0, "count": 0} for _ in range(12)]
    year_total = 0.0
    for p in payments:
        d = p.due_date
        cell = by_day.setdefault(d, {"total": 0.0, "count": 0, "items": []})
        cell["total"] += p.amount
        cell["count"] += 1
        cell["items"].append(
            {
                "service": p.service,
                "amount": p.amount,
                "is_paid": p.is_paid,
                "description": p.description,
            }
        )
        m = monthly[d.month - 1]
        m["total"] += p.amount
        m["count"] += 1
        if p.is_paid:
            m["paid"] += p.amount
        else:
            m["upcoming"] += p.amount
        year_total += p.amount

    max_total = max((c["total"] for c in by_day.values()), default=0.0)

    # Сетка GitHub: недели — столбцы, дни недели Пн..Вс — строки.
    # Старт — понедельник на/раньше 1 января.
    grid_start = start - timedelta(days=start.weekday())  # weekday(): Пн=0
    weeks = []
    month_labels = []  # {col, label}
    last_label_month = None
    cur = grid_start
    col = 0
    while cur <= end:
        week = []
        for _ in range(7):
            in_year = start <= cur <= end
            cell = by_day.get(cur)
            week.append(
                {
                    "date": cur.isoformat(),
                    "day": cur.day,
                    "in_year": in_year,
                    "is_today": cur == today,
                    "is_past": cur < today,
                    "alt_month": cur.month % 2 == 0,  # для чередования фона месяцев
                    "total": cell["total"] if cell else 0.0,
                    "count": cell["count"] if cell else 0,
                    "level": _level(cell["total"], max_total) if cell else 0,
                    "payments": cell["items"] if cell else [],
                }
            )
            cur += timedelta(days=1)
        # Подпись месяца — на первой неделе, где появляется новый месяц.
        first_in_year = next((dd for dd in week if dd["in_year"]), None)
        if first_in_year:
            m = int(first_in_year["date"][5:7])
            if m != last_label_month:
                month_labels.append({"col": col, "label": MONTHS_RU[m - 1]})
                last_label_month = m
        weeks.append(week)
        col += 1

    months_summary = [
        {
            "name": MONTHS_RU_FULL[i],
            "short": MONTHS_RU[i],
            "total": monthly[i]["total"],
            "paid": monthly[i]["paid"],
            "upcoming": monthly[i]["upcoming"],
            "count": monthly[i]["count"],
            "is_current": (i + 1 == today.month and year == today.year),
        }
        for i in range(12)
    ]
    max_month = max((m["total"] for m in months_summary), default=0.0) or 1.0

    upcoming = (
        db.query(Payment)
        .filter(Payment.user_id == user.id, Payment.is_paid == False, Payment.due_date >= today)  # noqa: E712
        .order_by(Payment.due_date.asc())
        .limit(8)
        .all()
    )

    # Для администратора — число заявок, ожидающих подтверждения.
    pending_count = 0
    if user.is_admin:
        pending_count = db.query(User).filter(User.is_approved == False).count()  # noqa: E712

    return render(
        request,
        "dashboard.html",
        weeks=weeks,
        month_labels=month_labels,
        months_summary=months_summary,
        max_month=max_month,
        year=year,
        prev_year=year - 1,
        next_year=year + 1,
        year_total=year_total,
        paid_total=sum(m["paid"] for m in months_summary),
        upcoming_total=sum(m["upcoming"] for m in months_summary),
        upcoming=upcoming,
        today=today,
        digest_msg=digest_msg,
        digest_err=digest_err,
        pending_count=pending_count,
    )


@router.post("/send-digest")
def send_digest(
    request: Request,
    period: int = Form(14),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Ручная отправка письма со списком предстоящих оплат за выбранный период."""
    today = date.today()
    q = db.query(Payment).filter(
        Payment.user_id == user.id,
        Payment.is_paid == False,  # noqa: E712
        Payment.due_date >= today,
    )
    if period > 0:  # period == 0 -> все предстоящие
        q = q.filter(Payment.due_date <= today + timedelta(days=period))
    payments = q.order_by(Payment.due_date.asc()).all()

    if not payments:
        return RedirectResponse("/?digest=empty", status_code=302)

    label = "все предстоящие" if period == 0 else f"{period} дн."
    html = digest_email_html(payments, label, today)
    ok = send_email(user.recipients, f"💳 {settings.app_name}: предстоящие оплаты", html)
    if ok:
        return RedirectResponse(f"/?digest=sent&n={len(payments)}", status_code=302)
    return RedirectResponse("/?digest=fail", status_code=302)
