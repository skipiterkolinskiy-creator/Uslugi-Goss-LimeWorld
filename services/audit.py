from datetime import datetime

from services.google_sheets import google_sheets_service


async def log_action(admin_id: int, username: str, action: str, passport: str | int, details: str) -> None:
    worksheet = google_sheets_service.worksheet("Логи")
    worksheet.append_row(
        [
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            admin_id,
            username,
            action,
            passport,
            details,
        ],
        value_input_option="USER_ENTERED",
    )
