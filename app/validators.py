"""전화번호·이메일 등 입력 검증과 포맷 함수 (static/js/form.js의 클라이언트 규칙과 같다)."""
import re
from datetime import date

MOBILE_RE = re.compile(r"^01[016789]\d{7,8}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_EN_RE = re.compile(r"^[A-Za-z \-]+$")

MSG = {
    "name": "이름을 입력해 주세요.",
    "name_len": "이름은 10자 이내로 입력해 주세요.",
    "mobile": "휴대전화 번호를 정확히 입력해 주세요.",
    "tel": "사무실 전화번호 형식이 올바르지 않습니다.",
    "email": "이메일 형식이 올바르지 않습니다.",
    "name_en": "영문 이름은 영문자만 입력해 주세요.",
    "hire_date": "입사일 형식이 올바르지 않습니다. (예: 2026-12-01)",
}


def only_digits(value):
    return re.sub(r"\D", "", value or "")


def format_phone(value):
    """원본 JS fmtPhone()과 같은 규칙으로 하이픈을 넣는다 (02 지역번호 처리 포함)."""
    d = only_digits(value)[:11]
    if d.startswith("02"):
        if len(d) <= 2:
            return d
        if len(d) <= 5:
            return d[:2] + "-" + d[2:]
        if len(d) <= 9:
            return d[:2] + "-" + d[2:len(d) - 4] + "-" + d[-4:]
        return d[:2] + "-" + d[2:6] + "-" + d[6:10]
    if len(d) <= 3:
        return d
    if len(d) <= 7:
        return d[:3] + "-" + d[3:]
    if len(d) <= 10:
        return d[:3] + "-" + d[3:6] + "-" + d[6:]
    return d[:3] + "-" + d[3:7] + "-" + d[7:]


def validate_name(value):
    v = (value or "").strip()
    if not v:
        return MSG["name"]
    if len(v) > 10:
        return MSG["name_len"]
    return None


def validate_mobile(value):
    return None if MOBILE_RE.match(only_digits(value)) else MSG["mobile"]


def validate_tel(value):
    d = only_digits(value)
    if not d:
        return None
    return None if 9 <= len(d) <= 11 else MSG["tel"]


def validate_email(value):
    v = (value or "").strip()
    if not v:
        return None
    return None if len(v) <= 100 and EMAIL_RE.match(v) else MSG["email"]


def validate_name_en(value):
    v = (value or "").strip()
    if not v:
        return None
    return None if len(v) <= 40 and NAME_EN_RE.match(v) and re.search(r"[A-Za-z]", v) else MSG["name_en"]


def complete_email(value, domain):
    """F-15: 아이디만 입력하면 설정된 도메인을 붙인다."""
    v = (value or "").strip()
    if v and "@" not in v and domain:
        return f"{v}@{domain}"
    return v


def parse_date(value):
    v = (value or "").strip()
    if not v:
        return None, None
    try:
        return date.fromisoformat(v), None
    except ValueError:
        return None, MSG["hire_date"]


def validate_employee(form, email_domain=None):
    """폼(dict 유사 객체)을 검증한다. (정리된 데이터, {필드: 오류 메시지})를 돌려준다.

    부서·직급(DB 조회 필요)은 뷰에서 따로 검증한다.
    """
    get = lambda k: (form.get(k) or "")
    email = complete_email(get("email"), email_domain)
    errors = {}
    for field, fn, value in (
        ("name", validate_name, get("name")),
        ("mobile", validate_mobile, get("mobile")),
        ("tel", validate_tel, get("tel")),
        ("email", validate_email, email),
        ("name_en", validate_name_en, get("name_en")),
    ):
        msg = fn(value)
        if msg:
            errors[field] = msg
    hire_date, msg = parse_date(get("hire_date"))
    if msg:
        errors["hire_date"] = msg

    data = {
        "name": get("name").strip(),
        "name_en": get("name_en").strip() or None,
        "mobile": only_digits(get("mobile")),
        "tel": only_digits(get("tel")) or None,
        "email": email or None,
        "hire_date": hire_date,
    }
    return data, errors
