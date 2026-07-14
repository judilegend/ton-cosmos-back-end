from app.services.time_utils import parse_birth_time


def test_parse_birth_time_supports_hh_mm_ss_string():
    assert parse_birth_time("12:00:00") == "12:00:00"


def test_parse_birth_time_supports_hh_mm_string():
    assert parse_birth_time("12:00") == "12:00"
