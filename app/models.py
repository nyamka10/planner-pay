from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Почта, на которую приходят напоминания (может отличаться от email входа).
    notify_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Регистрация подтверждается администратором.
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    payments: Mapped[list["Payment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def recipients(self) -> list[str]:
        """Список адресов для напоминаний (хранится через запятую/перенос строки)."""
        import re

        raw = (self.notify_email or self.email or "").strip()
        parts = re.split(r"[,;\n\s]+", raw)
        # Сохраняем порядок и убираем дубли.
        seen, result = set(), []
        for p in parts:
            p = p.strip()
            if p and p.lower() not in seen:
                seen.add(p.lower())
                result.append(p)
        return result

    @property
    def recipient(self) -> str:
        """Первый адрес (для совместимости и компактного отображения)."""
        r = self.recipients
        return r[0] if r else self.email

    @property
    def recipients_str(self) -> str:
        return ", ".join(self.recipients)


class Payment(Base):
    """Одна оплата (одно событие на дату). Продление создаёт новую запись."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    due_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    service: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Флаги, чтобы не отправлять одно и то же напоминание дважды.
    notified_14: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_1: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="payments")
