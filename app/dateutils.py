"""Небольшие помощники по датам без внешних зависимостей."""
import calendar
from datetime import date


def add_months(d: date, months: int) -> date:
    """Прибавляет месяцы к дате, корректно обрабатывая концы месяцев
    (например, 31 января + 1 месяц -> 28/29 февраля)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)
