import secrets
from datetime import datetime

from database.models import CitizenData, SearchCitizen
from services.google_sheets import GOS_HEADERS, get_rows_as_dicts, google_sheets_service


def normalize_username(value: str) -> str:
    return value.strip().lower().removeprefix("@")


def row_to_citizen(row: dict[str, str]) -> SearchCitizen:
    fio = " ".join([row.get("Фамилия", ""), row.get("Имя", ""), row.get("Отчество", "")]).strip()
    return SearchCitizen(
        passport=int(row.get("Паспорт") or 0),
        telegram_id=row.get("Telegram ID", ""),
        username=row.get("Username", ""),
        fio=fio,
        age=row.get("Возраст", ""),
        status=row.get("Статус", ""),
        wanted=row.get("Розыск", ""),
        fines=row.get("Штрафы", ""),
        licenses=row.get("Лицензии", ""),
        job=row.get("Работа", ""),
        raw=row,
    )


class CitizensService:
    def rows(self) -> list[dict[str, str]]:
        return get_rows_as_dicts(google_sheets_service.worksheet("Персонажи"))

    async def find_by_telegram(self, telegram_id: int) -> SearchCitizen | None:
        for row in self.rows():
            if row.get("Telegram ID") == str(telegram_id):
                return row_to_citizen(row)
        return None

    async def find_by_code(self, code: str) -> SearchCitizen | None:
        needle = code.strip().upper()
        for row in self.rows():
            if row.get("Код входа", "").strip().upper() == needle:
                return row_to_citizen(row)
        return None

    async def find_by_passport(self, passport: int) -> SearchCitizen | None:
        for row in self.rows():
            if row.get("Паспорт") == str(passport):
                return row_to_citizen(row)
        return None

    async def search(self, query: str) -> list[SearchCitizen]:
        return search_rows(self.rows(), query)

    async def max_passport(self) -> int:
        return max_passport_in_rows(self.rows())

    async def append(self, citizen: CitizenData) -> None:
        worksheet = google_sheets_service.worksheet("Персонажи")
        values = [
            citizen.passport, citizen.login_code, citizen.telegram_id, citizen.username,
            citizen.last_name, citizen.first_name, citizen.patronymic, citizen.age,
            citizen.birthdate, citizen.gender, citizen.first_citizenship, citizen.second_citizenship,
            citizen.nationality, citizen.skin, citizen.hair, citizen.eyes, citizen.appearance,
            citizen.military, citizen.photo_file_id, citizen.status, citizen.wanted, citizen.fines,
            citizen.licenses, citizen.job, citizen.notes, citizen.registered_at or datetime.now().strftime("%d.%m.%Y %H:%M"),
        ]
        worksheet.append_row(values, value_input_option="USER_ENTERED")

    async def update_field(self, passport: int, field: str, value: str) -> None:
        worksheet = google_sheets_service.worksheet("Персонажи")
        headers = worksheet.row_values(1)
        rows = worksheet.get_all_values()
        if field not in headers:
            return
        col = headers.index(field) + 1
        for row_index, row in enumerate(rows[1:], start=2):
            if row and row[0] == str(passport):
                worksheet.update_cell(row_index, col, value)
                return

    async def add_login_binding(self, citizen: SearchCitizen, telegram_id: int, username: str) -> None:
        await self.update_field(citizen.passport, "Telegram ID", str(telegram_id))
        await self.update_field(citizen.passport, "Username", username)

    def format_card(self, citizen: SearchCitizen) -> str:
        dead = "\n⚫ <b>ПЕРСОНАЖ ЧИСЛИТСЯ МЁРТВЫМ</b>\n" if citizen.status.lower() == "мёртв" else ""
        return (
            f"{dead}<b>Паспорт №{citizen.passport}</b>\n"
            f"ФИО: {citizen.fio}\n"
            f"Возраст: {citizen.age}\n"
            f"Статус: {citizen.status or 'Жив'}\n"
            f"Розыск: {citizen.wanted or 'Нет'}\n"
            f"Штрафы: {citizen.fines or '0'}\n"
            f"Лицензии: {citizen.licenses or 'Нет'}\n"
            f"Работа: {citizen.job or 'Не указана'}"
        )

    def make_login_code(self, passport: int) -> str:
        return f"UG-{passport}-{secrets.token_hex(2).upper()}"


def max_passport_in_rows(rows: list[dict[str, str]]) -> int:
    values: list[int] = []
    for row in rows:
        text = str(row.get("Паспорт", "")).strip()
        if text.isdigit():
            values.append(int(text))
    return max(values, default=0)


def search_rows(rows: list[dict[str, str]], query: str) -> list[SearchCitizen]:
    needle = query.strip().lower()
    username = normalize_username(needle)
    found: list[SearchCitizen] = []
    for row in rows:
        fio = " ".join([row.get("Фамилия", ""), row.get("Имя", ""), row.get("Отчество", "")]).strip()
        haystack = " ".join([
            row.get("Паспорт", ""),
            row.get("Telegram ID", ""),
            normalize_username(row.get("Username", "")),
            fio.lower(),
        ]).lower()
        if needle in haystack or username in haystack:
            found.append(row_to_citizen(row))
    return found


citizens_service = CitizensService()
