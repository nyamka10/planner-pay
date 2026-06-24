from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки берутся из переменных окружения (.env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- База данных ---
    database_url: str = "sqlite:////data/planner_pay.db"

    # --- Безопасность сессий ---
    secret_key: str = "change-me-please"
    session_max_age: int = 60 * 60 * 24 * 14  # 14 дней

    # --- Первый администратор (создаётся при старте, если его нет) ---
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_email: str = "admin@example.com"

    # --- SMTP (общий сервер отправки) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True  # STARTTLS
    smtp_use_ssl: bool = False  # SSL (обычно порт 465)

    # --- Планировщик ---
    timezone: str = "Europe/Moscow"
    reminder_hour: int = 9  # во сколько часов проверять и слать напоминания
    reminder_minute: int = 0
    remind_days_before: list[int] = [14, 1]  # за сколько дней напоминать

    # --- Прочее ---
    currency: str = "₽"
    app_name: str = "Planner Pay"


settings = Settings()
