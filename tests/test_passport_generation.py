from services.citizens import max_passport_in_rows


def test_next_passport_uses_maximum_from_both_tables():
    gos = [{"Паспорт": "615"}, {"Паспорт": "abc"}]
    mvd = [{"Паспорт": "700"}]
    assert max(max_passport_in_rows(gos), max_passport_in_rows(mvd)) + 1 == 701
