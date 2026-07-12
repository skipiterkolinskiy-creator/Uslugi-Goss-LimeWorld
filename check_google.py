import asyncio

from config import validate_settings
from services.citizens import citizens_service
from services.google_sheets import GOS_HEADERS, get_rows_as_dicts, google_sheets_service
from services.license_tests import LICENSES, license_tests_service
from services.mvd_sync import mvd_sync_service


def assert_unique_headers(title: str, headers: list[str]) -> None:
    cleaned = [h for h in headers if h]
    if len(cleaned) != len(set(cleaned)):
        raise RuntimeError(f"В листе {title} есть повторяющиеся заголовки")


async def main() -> None:
    validate_settings()
    await google_sheets_service.initialize()
    for title in GOS_HEADERS:
        worksheet = google_sheets_service.worksheet(title)
        headers = worksheet.row_values(1)
        assert_unique_headers(title, headers)
        print(f"OK: лист {title}")

    mvd_headers = mvd_sync_service.headers()
    assert_unique_headers("МВД", mvd_headers)
    next_passport = max(await citizens_service.max_passport(), await mvd_sync_service.max_passport()) + 1
    print(f"OK: следующий паспорт {next_passport}")

    for query in ["615", "@skipiter", "Шарпов Максим"]:
        result = await citizens_service.search(query)
        print(f"OK: поиск {query!r}: {len(result)}")

    assert LICENSES["AUTO"].passing_score == 13
    assert LICENSES["TRUCK"].bank == "road"
    assert LICENSES["WEAPON"].passing_score == 14
    assert not license_tests_service.can_apply_hunting("")
    print("OK: лицензии и зависимость охоты")

    rows = get_rows_as_dicts(google_sheets_service.worksheet("Персонажи"))
    print(f"OK: безопасное чтение строк персонажей: {len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
