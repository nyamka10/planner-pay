import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from .config import settings

logger = logging.getLogger("calendar_pay.email")


def _sender():
    """Адрес отправителя обязан совпадать с аутентифицированным ящиком
    (иначе SMTP-серверы вроде Яндекса/Gmail отклоняют письмо: 553 Sender rejected).
    SMTP_FROM используется только для красивого имени, если его адрес совпадает
    с SMTP_USER; в остальных случаях берём сам SMTP_USER.
    """
    sender_addr = settings.smtp_user or parseaddr(settings.smtp_from)[1]
    display_name = settings.app_name
    if settings.smtp_from:
        name, addr = parseaddr(settings.smtp_from)
        if addr and addr == sender_addr and name:
            display_name = name
    return sender_addr, formataddr((display_name, sender_addr))


def send_email(to, subject: str, body_html: str, body_text: str = "") -> bool:
    """Отправляет письмо через общий SMTP-сервер из .env.

    `to` — строка или список адресов: письмо уйдёт на все указанные.
    Возвращает True при успехе. При незаполненном SMTP — просто логирует
    (удобно для локальной разработки без почтового сервера).
    """
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        logger.warning("Нет адресов получателей. Письмо не отправлено: %s", subject)
        return False

    if not settings.smtp_host:
        logger.warning("SMTP не настроен. Письмо для %s не отправлено: %s", recipients, subject)
        return False

    sender_addr, from_header = _sender()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = ", ".join(recipients)
    msg.set_content(body_text or "Откройте письмо в HTML-режиме.")
    msg.add_alternative(body_html, subtype="html")

    try:
        if settings.smtp_use_ssl:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
        with server:
            server.ehlo()
            if settings.smtp_use_tls and not settings.smtp_use_ssl:
                server.starttls()
                server.ehlo()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg, from_addr=sender_addr, to_addrs=recipients)
        logger.info("Письмо отправлено: %s -> %s", subject, recipients)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка отправки письма для %s", recipients)
        return False


def digest_email_html(payments: list, days, today) -> str:
    """Сводное письмо со списком предстоящих оплат за выбранный период."""
    rows = ""
    total = 0.0
    for p in payments:
        total += p.amount
        days_left = (p.due_date - today).days
        when = "сегодня" if days_left == 0 else ("завтра" if days_left == 1 else f"через {days_left} дн.")
        desc = f'<div style="color:#8b949e;font-size:12px;">{p.description}</div>' if p.description else ""
        rows += f"""\
        <tr>
          <td style="padding:10px 8px;border-bottom:1px solid #d0d7de;white-space:nowrap;">
            <b>{p.due_date:%d.%m.%Y}</b><div style="color:#8b949e;font-size:12px;">{when}</div>
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid #d0d7de;">
            <b>{p.service}</b>{desc}
          </td>
          <td style="padding:10px 8px;border-bottom:1px solid #d0d7de;text-align:right;white-space:nowrap;">
            {p.amount:,.2f} {settings.currency}
          </td>
        </tr>"""

    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f8fa;padding:24px;">
  <div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #d0d7de;border-radius:12px;overflow:hidden;">
    <div style="background:#0d1117;color:#fff;padding:18px 24px;font-size:18px;font-weight:600;">
      💳 {settings.app_name}: предстоящие оплаты ({days})
    </div>
    <div style="padding:24px;">
      <table style="width:100%;border-collapse:collapse;font-size:14px;color:#1f2328;">
        {rows}
        <tr>
          <td colspan="2" style="padding:14px 8px 0;font-weight:700;font-size:16px;">Итого</td>
          <td style="padding:14px 8px 0;text-align:right;font-weight:700;font-size:16px;white-space:nowrap;">
            {total:,.2f} {settings.currency}
          </td>
        </tr>
      </table>
      <p style="margin:20px 0 0;font-size:13px;color:#8b949e;">
        Письмо сформировано вручную из сервиса {settings.app_name}.
      </p>
    </div>
  </div>
</div>"""


def reminder_email_html(service: str, amount: float, due_date, days_left: int, description: str) -> str:
    when = "завтра" if days_left == 1 else f"через {days_left} дн."
    desc_block = (
        f'<p style="margin:8px 0 0;color:#57606a;font-size:14px;">{description}</p>'
        if description
        else ""
    )
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f6f8fa;padding:24px;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #d0d7de;border-radius:12px;overflow:hidden;">
    <div style="background:#0d1117;color:#fff;padding:18px 24px;font-size:18px;font-weight:600;">
      💳 {settings.app_name}: предстоит оплата
    </div>
    <div style="padding:24px;">
      <p style="margin:0 0 16px;font-size:16px;color:#1f2328;">
        Оплата <b>{service}</b> {when} — <b>{due_date:%d.%m.%Y}</b>.
      </p>
      <div style="background:#f6f8fa;border:1px solid #d0d7de;border-radius:10px;padding:16px;">
        <div style="font-size:28px;font-weight:700;color:#1f2328;">{amount:,.2f} {settings.currency}</div>
        {desc_block}
      </div>
      <p style="margin:20px 0 0;font-size:13px;color:#8b949e;">
        Это автоматическое напоминание сервиса {settings.app_name}.
      </p>
    </div>
  </div>
</div>"""
