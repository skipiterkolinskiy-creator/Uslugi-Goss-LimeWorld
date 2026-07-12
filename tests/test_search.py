from services.citizens import search_rows


ROWS = [
    {
        "Паспорт": "615",
        "Telegram ID": "8548608434",
        "Username": "Skipiter",
        "Фамилия": "Шарпов",
        "Имя": "Максим",
        "Отчество": "Олегович",
        "Возраст": "25",
        "Статус": "Жив",
        "Розыск": "Нет",
        "Штрафы": "0",
        "Лицензии": "WEAPON",
        "Работа": "Юрист",
    }
]


def test_search_by_passport():
    assert search_rows(ROWS, "615")[0].passport == 615


def test_search_by_telegram_id():
    assert search_rows(ROWS, "8548608434")[0].fio == "Шарпов Максим Олегович"


def test_search_by_username():
    assert search_rows(ROWS, "@skipiter")[0].passport == 615


def test_search_by_partial_fio():
    assert search_rows(ROWS, "Шарпов Максим")[0].passport == 615
