from datetime import datetime

from services.google_sheets import google_sheets_service


async def append_medical(request_id: int, payload: dict, admin: str) -> None:
    google_sheets_service.worksheet("Медкарты").append_row(
        [
            request_id,
            payload.get("passport", ""),
            payload.get("telegram_id", ""),
            payload.get("height", ""),
            payload.get("weight", ""),
            payload.get("blood", ""),
            payload.get("allergies", ""),
            payload.get("chronic", ""),
            payload.get("notes", ""),
            "Одобрена",
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            admin,
        ],
        value_input_option="USER_ENTERED",
    )


async def append_license(request_id: int, payload: dict, admin: str, status: str, reason: str = "") -> None:
    google_sheets_service.worksheet("Лицензии").append_row(
        [
            request_id,
            payload.get("passport", ""),
            payload.get("telegram_id", ""),
            payload.get("license_code", ""),
            payload.get("license_title", ""),
            payload.get("score", ""),
            payload.get("max_score", ""),
            payload.get("fee", ""),
            payload.get("payment_photo_file_id", ""),
            status,
            reason,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            admin,
        ],
        value_input_option="USER_ENTERED",
    )


async def append_fine(passport: int, telegram_id: str, amount: int, reason: str, admin: str, status: str = "Не оплачен") -> None:
    worksheet = google_sheets_service.worksheet("Штрафы")
    next_id = max(len(worksheet.get_all_values()), 1)
    worksheet.append_row(
        [
            next_id,
            passport,
            telegram_id,
            amount,
            reason,
            admin,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            status,
            "",
            "",
        ],
        value_input_option="USER_ENTERED",
    )


async def append_wanted(passport: int, reason: str, admin: str, active: str = "Да") -> None:
    worksheet = google_sheets_service.worksheet("Розыск")
    next_id = max(len(worksheet.get_all_values()), 1)
    worksheet.append_row(
        [
            next_id,
            passport,
            reason,
            admin,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            active,
            "",
            "",
        ],
        value_input_option="USER_ENTERED",
    )
