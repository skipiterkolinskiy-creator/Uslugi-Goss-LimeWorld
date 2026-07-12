import logging
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

GOS_HEADERS = {
    "Персонажи": [
        "Паспорт", "Код входа", "Telegram ID", "Username", "Фамилия", "Имя", "Отчество",
        "Возраст", "Дата рождения", "Пол", "Первое гражданство", "Второе гражданство",
        "Национальность", "Цвет кожи", "Цвет волос", "Цвет глаз", "Описание внешности",
        "Военный билет", "Фото file_id", "Статус", "Розыск", "Штрафы", "Лицензии",
        "Работа", "Примечания", "Дата регистрации",
    ],
    "Заявки": [
        "ID", "Тип", "Telegram ID", "Username", "Паспорт", "ФИО", "Данные JSON",
        "Статус", "Причина отказа", "Создано", "Рассмотрено", "Администратор",
    ],
    "Медкарты": [
        "ID", "Паспорт", "Telegram ID", "Рост", "Вес", "Группа крови", "Аллергии",
        "Хронические заболевания", "Примечания", "Статус", "Дата создания",
        "Дата одобрения", "Администратор",
    ],
    "Лицензии": [
        "ID", "Паспорт", "Telegram ID", "Код лицензии", "Название", "Баллы", "Максимум",
        "Пошлина", "Скрин оплаты file_id", "Статус", "Причина отказа", "Дата заявления",
        "Дата решения", "Администратор",
    ],
    "Штрафы": [
        "ID", "Паспорт", "Telegram ID", "Сумма", "Причина", "Кто выдал", "Дата выдачи",
        "Статус", "Скрин оплаты file_id", "Дата оплаты",
    ],
    "Розыск": [
        "ID", "Паспорт", "Причина", "Кто объявил", "Дата", "Активен", "Дата снятия", "Кто снял",
    ],
    "Логи": [
        "Дата", "Telegram ID администратора", "Username администратора", "Действие", "Паспорт", "Подробности",
    ],
}


def get_rows_as_dicts(worksheet: Any) -> list[dict[str, str]]:
    values = worksheet.get_all_values()
    if not values:
        return []
    headers = [str(value).strip() for value in values[0]]
    while headers and not headers[-1]:
        headers.pop()
    used: set[str] = set()
    normalized_headers: list[str] = []
    for index, header in enumerate(headers, start=1):
        if not header:
            header = f"Без названия {index}"
        original = header
        counter = 2
        while header in used:
            header = f"{original} {counter}"
            counter += 1
        used.add(header)
        normalized_headers.append(header)
    result: list[dict[str, str]] = []
    for raw_row in values[1:]:
        row = raw_row[: len(normalized_headers)]
        row += [""] * (len(normalized_headers) - len(row))
        result.append(dict(zip(normalized_headers, row)))
    return result


def ensure_headers(worksheet: Any, headers: list[str]) -> None:
    values = worksheet.get_all_values()
    if not values:
        worksheet.update("A1", [headers])
        return
    current = [str(value).strip() for value in values[0]]
    changed = False
    for header in headers:
        if header not in current:
            current.append(header)
            changed = True
    if changed or current[: len(headers)] != headers:
        ordered = headers + [h for h in current if h and h not in headers]
        worksheet.update("A1", [ordered])


class GoogleSheetsService:
    def __init__(self) -> None:
        self.gos = None
        self.mvd = None

    async def initialize(self) -> None:
        credentials = Credentials.from_service_account_file(settings.google_credentials_file, scopes=SCOPES)
        client = gspread.authorize(credentials)
        self.gos = client.open_by_key(settings.gos_spreadsheet_id)
        self.mvd = client.open_by_key(settings.mvd_spreadsheet_id)
        for title, headers in GOS_HEADERS.items():
            worksheet = self.get_or_create(self.gos, title)
            ensure_headers(worksheet, headers)

    def get_or_create(self, spreadsheet: Any, title: str) -> Any:
        try:
            return spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=title, rows=2000, cols=40)
            logger.info("Создан лист %s", title)
            return worksheet

    def worksheet(self, title: str) -> Any:
        if self.gos is None:
            raise RuntimeError("Google Sheets ещё не инициализирован")
        return self.gos.worksheet(title)

    def mvd_first_sheet(self) -> Any:
        if self.mvd is None:
            raise RuntimeError("Google Sheets ещё не инициализирован")
        return self.mvd.sheet1


google_sheets_service = GoogleSheetsService()
