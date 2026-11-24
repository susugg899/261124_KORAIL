import pytest

from app.validators import (MSG, complete_email, format_phone, validate_email, validate_employee,
                            validate_mobile, validate_name, validate_name_en, validate_tel)


@pytest.mark.parametrize("raw, expected", [
    ("01012345678", "010-1234-5678"),      # 010 11자리
    ("010-1234-5678", "010-1234-5678"),
    ("0111234567", "011-123-4567"),        # 011 10자리
    ("021234567", "02-123-4567"),          # 02 9자리
    ("0212345678", "02-1234-5678"),        # 02 10자리
    ("0420000000", "042-000-0000"),
    ("", ""),                              # 빈 값
    (None, ""),
    ("010", "010"),
    ("0101234", "010-1234"),
    ("02123", "02-123"),
    ("010123456789999", "010-1234-5678"),  # 11자리 초과는 잘라낸다
])
def test_format_phone(raw, expected):
    assert format_phone(raw) == expected


@pytest.mark.parametrize("value, ok", [
    ("홍길동", True), ("  홍길동  ", True), ("가" * 10, True),
    ("", False), ("   ", False), ("가" * 11, False),
])
def test_name(value, ok):
    assert (validate_name(value) is None) == ok


@pytest.mark.parametrize("value, ok", [
    ("010-1234-5678", True), ("01012345678", True), ("0111234567", True), ("019-123-4567", True),
    ("012-1234-5678", False), ("010-123-456", False), ("010123456789", False), ("02-1234-5678", False), ("", False),
])
def test_mobile(value, ok):
    assert (validate_mobile(value) is None) == ok


@pytest.mark.parametrize("value, ok", [
    ("", True), ("02-123-4567", True), ("042-000-0000", True), ("010-1234-5678", True),
    ("02-123-456", False), ("0421234567890", False),
])
def test_tel(value, ok):
    assert (validate_tel(value) is None) == ok


@pytest.mark.parametrize("value, ok", [
    ("", True), ("gildong@korail.com", True), ("a@b.co", True),
    ("gildong", False), ("a@b", False), ("a b@c.com", False), ("a" * 95 + "@x.com", False),
])
def test_email(value, ok):
    assert (validate_email(value) is None) == ok


@pytest.mark.parametrize("value, ok", [
    ("", True), ("Hong Gil-dong", True), ("A" * 40, True),
    ("홍길동", False), ("Hong1", False), ("A" * 41, False), ("---", False),
])
def test_name_en(value, ok):
    assert (validate_name_en(value) is None) == ok


def test_complete_email():
    assert complete_email("gildong", "korail.com") == "gildong@korail.com"
    assert complete_email("a@b.com", "korail.com") == "a@b.com"
    assert complete_email("", "korail.com") == ""


def test_validate_employee_cleans_data():
    data, errors = validate_employee({
        "name": " 홍길동 ", "mobile": "010-1234-5678", "tel": "042-000-0000",
        "email": "gildong", "hire_date": "2026-12-01",
    }, "korail.com")
    assert errors == {}
    assert data["name"] == "홍길동"
    assert data["mobile"] == "01012345678"
    assert data["tel"] == "0420000000"
    assert data["email"] == "gildong@korail.com"
    assert data["hire_date"].isoformat() == "2026-12-01"


def test_validate_employee_errors():
    _, errors = validate_employee({"name": "", "mobile": "123", "hire_date": "2026-13-01"})
    assert errors["name"] == MSG["name"]
    assert errors["mobile"] == MSG["mobile"]
    assert "hire_date" in errors
