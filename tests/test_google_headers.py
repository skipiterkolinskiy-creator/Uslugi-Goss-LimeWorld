from services.google_sheets import get_rows_as_dicts


class FakeWorksheet:
    def get_all_values(self):
        return [
            ["Паспорт", "", "Паспорт", ""],
            ["615", "x", "616", "tail"],
        ]


def test_safe_headers_are_unique_and_not_empty():
    rows = get_rows_as_dicts(FakeWorksheet())
    assert rows[0]["Паспорт"] == "615"
    assert rows[0]["Без названия 2"] == "x"
    assert rows[0]["Паспорт 2"] == "616"
