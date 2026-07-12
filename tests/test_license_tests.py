from services.license_tests import LICENSES, license_tests_service


def test_exam_thresholds():
    assert LICENSES["AUTO"].questions_count == 15
    assert LICENSES["AUTO"].passing_score == 13
    assert LICENSES["TRUCK"].bank == "road"
    assert LICENSES["TRUCK"].passing_score == 13
    assert LICENSES["MOTO"].questions_count == 15
    assert LICENSES["MOTO"].passing_score == 13
    assert LICENSES["WEAPON"].questions_count == 16
    assert LICENSES["WEAPON"].passing_score == 14


def test_fee_only_licenses_and_hunting_dependency():
    assert LICENSES["FISHING"].questions_count == 0
    assert LICENSES["HUNTING"].requires_license == "WEAPON"
    assert not license_tests_service.can_apply_hunting("")
    assert license_tests_service.can_apply_hunting("AUTO, WEAPON")
