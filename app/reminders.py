"""Логика рассылки напоминаний и продления оплат."""
import logging
from datetime import date

from sqlalchemy.orm import Session

from .dateutils import add_months

from .config import settings
from .email_utils import reminder_email_html, send_email
from .models import Payment

logger = logging.getLogger("calendar_pay.reminders")


def process_due_reminders(db: Session, today: date | None = None) -> int:
    """Проходит по всем неоплаченным записям и шлёт напоминания
    за N дней до даты (по умолчанию 14 и 1). Возвращает число отправленных писем.
    """
    today = today or date.today()
    sent = 0

    payments = db.query(Payment).filter(Payment.is_paid == False).all()  # noqa: E712
    for p in payments:
        days_left = (p.due_date - today).days
        if days_left < 0:
            continue

        # 14 дней
        if 14 in settings.remind_days_before and days_left == 14 and not p.notified_14:
            if _send(p, days_left):
                p.notified_14 = True
                sent += 1
        # 1 день
        if 1 in settings.remind_days_before and days_left == 1 and not p.notified_1:
            if _send(p, days_left):
                p.notified_1 = True
                sent += 1

    db.commit()
    logger.info("Обработка напоминаний завершена. Отправлено: %d", sent)
    return sent


def _send(p: Payment, days_left: int) -> bool:
    recipients = p.user.recipients
    if not recipients:
        logger.warning("У пользователя %s нет почты для напоминаний", p.user.username)
        return False
    html = reminder_email_html(p.service, p.amount, p.due_date, days_left, p.description)
    subject = f"💳 {p.service}: оплата { 'завтра' if days_left == 1 else f'через {days_left} дн.'}"
    return send_email(recipients, subject, html)


def renew_payment(db: Session, payment: Payment, new_due_date=None, new_amount=None) -> Payment:
    """Помечает текущую запись оплаченной и создаёт новую на следующий период.
    Так копится история оплат, а напоминания начинаются заново.

    new_due_date / new_amount — дата и сумма следующего платежа. Если не заданы,
    берутся +1 месяц и текущая сумма.
    """
    from datetime import datetime

    payment.is_paid = True
    payment.paid_at = datetime.utcnow()

    new_payment = Payment(
        user_id=payment.user_id,
        due_date=new_due_date or add_months(payment.due_date, 1),
        service=payment.service,
        amount=payment.amount if new_amount is None else new_amount,
        description=payment.description,
        is_paid=False,
        notified_14=False,
        notified_1=False,
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return new_payment
