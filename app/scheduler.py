import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .database import SessionLocal
from .reminders import process_due_reminders, send_monthly_reports

logger = logging.getLogger("calendar_pay.scheduler")
scheduler = BackgroundScheduler(timezone=settings.timezone)


def _daily_job():
    db = SessionLocal()
    try:
        process_due_reminders(db)
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка в задаче рассылки напоминаний")
    finally:
        db.close()


def _monthly_job():
    db = SessionLocal()
    try:
        send_monthly_reports(db)
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка в задаче ежемесячного отчёта")
    finally:
        db.close()


def start_scheduler():
    if scheduler.running:
        return
    # Ежедневные напоминания (за 14 и 1 день).
    scheduler.add_job(
        _daily_job,
        CronTrigger(hour=settings.reminder_hour, minute=settings.reminder_minute),
        id="daily_reminders",
        replace_existing=True,
    )
    # Ежемесячный отчёт — 1-го числа.
    scheduler.add_job(
        _monthly_job,
        CronTrigger(day=1, hour=settings.reminder_hour, minute=settings.reminder_minute),
        id="monthly_report",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Планировщик запущен: напоминания ежедневно в %02d:%02d, отчёт 1-го числа (%s)",
        settings.reminder_hour,
        settings.reminder_minute,
        settings.timezone,
    )
