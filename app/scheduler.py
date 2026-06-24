import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .database import SessionLocal
from .reminders import process_due_reminders

logger = logging.getLogger("calendar_pay.scheduler")
scheduler = BackgroundScheduler(timezone=settings.timezone)


def _job():
    db = SessionLocal()
    try:
        process_due_reminders(db)
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка в задаче рассылки напоминаний")
    finally:
        db.close()


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(
        _job,
        CronTrigger(hour=settings.reminder_hour, minute=settings.reminder_minute),
        id="daily_reminders",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Планировщик запущен: ежедневно в %02d:%02d (%s)",
        settings.reminder_hour,
        settings.reminder_minute,
        settings.timezone,
    )
