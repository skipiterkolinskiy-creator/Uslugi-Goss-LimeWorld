from database.models import CitizenData
from services.google_sheets import get_rows_as_dicts, google_sheets_service


MVD_FIELD_MAP = {
    "Паспорт": "Паспорт",
    "Username": "Username",
    "Фамилия": "Фамилия",
    "Имя": "Имя",
    "Отчество": "Отчество",
    "Возраст": "Возраст",
    "Дата рождения": "Дата рождения",
    "Пол": "Пол",
    "Статус": "Статус",
    "Лицензии": "Лицензии",
    "Работа": "Работа",
    "Примечания": "Примечания",
    "Розыск": "Розыск",
    "Штрафы": "Штрафы",
}


class MvdSyncService:
    def worksheet(self):
        return google_sheets_service.mvd_first_sheet()

    def headers(self) -> list[str]:
        return [str(x).strip() for x in self.worksheet().row_values(1)]

    async def max_passport(self) -> int:
        rows = get_rows_as_dicts(self.worksheet())
        values = []
        for row in rows:
            text = str(row.get("Паспорт", "")).strip()
            if text.isdigit():
                values.append(int(text))
        return max(values, default=0)

    async def create_mvd_citizen(self, citizen: CitizenData) -> None:
        headers = self.headers()
        source = {
            "Паспорт": citizen.passport,
            "Username": citizen.username,
            "Фамилия": citizen.last_name,
            "Имя": citizen.first_name,
            "Отчество": citizen.patronymic,
            "Возраст": citizen.age,
            "Дата рождения": citizen.birthdate,
            "Пол": citizen.gender,
            "Статус": citizen.status,
            "Лицензии": citizen.licenses,
            "Работа": citizen.job,
            "Примечания": citizen.notes,
        }
        row = [source.get(header, "") for header in headers]
        self.worksheet().append_row(row, value_input_option="USER_ENTERED")

    async def update_by_header(self, passport: int, header: str, value: str) -> None:
        headers = self.headers()
        if header not in headers or "Паспорт" not in headers:
            return
        passport_col = headers.index("Паспорт")
        target_col = headers.index(header) + 1
        values = self.worksheet().get_all_values()
        for row_index, row in enumerate(values[1:], start=2):
            if len(row) > passport_col and row[passport_col] == str(passport):
                self.worksheet().update_cell(row_index, target_col, value)
                return

    async def update_mvd_status(self, passport: int, status: str) -> None:
        await self.update_by_header(passport, "Статус", status)

    async def update_mvd_licenses(self, passport: int, licenses: str) -> None:
        await self.update_by_header(passport, "Лицензии", licenses)

    async def update_mvd_wanted(self, passport: int, wanted: str) -> None:
        await self.update_by_header(passport, "Розыск", wanted)

    async def update_mvd_fines(self, passport: int, fines: str) -> None:
        await self.update_by_header(passport, "Штрафы", fines)


mvd_sync_service = MvdSyncService()
