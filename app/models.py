import json
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, func
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .validators import format_phone

SETTING_DEFAULTS = {
    "company_name": "한국철도공사",
    "company_name_en": "KORAIL",
    "address": "대전광역시 동구 중앙로 240",
    "email_domain": "korail.com",
}

POSITION_DEFAULTS = ["사원", "주임", "대리", "과장", "차장", "부장", "팀장", "역장", "기관사", "열차팀장"]
# 예시 부서 (관리 화면에서 실제 조직에 맞게 바꾼다)
DEPARTMENT_DEFAULTS = ["경영기획본부", "여객사업본부", "광역철도본부", "물류사업본부", "기술본부", "안전본부"]

SIDE_LABELS = {"front": "앞면", "back": "뒷면", "both": "앞·뒷면"}
METHOD_LABELS = {"png": "PNG", "print": "인쇄", "zip": "ZIP"}


KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어 고정 오프셋으로 충분하다


def now():
    """한국 시간(naive). 서버가 UTC(Vercel)여도 화면·이력에 한국 시간이 기록된다."""
    return datetime.now(KST).replace(tzinfo=None, microsecond=0)


class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Integer, nullable=False, default=1)


class Position(db.Model):
    __tablename__ = "positions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Integer, nullable=False, default=1)


class Employee(db.Model):
    __tablename__ = "employees"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, nullable=False)
    name_en = db.Column(db.Text)
    mobile = db.Column(db.Text, nullable=False, unique=True)
    tel = db.Column(db.Text)
    email = db.Column(db.Text)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    position_id = db.Column(db.Integer, db.ForeignKey("positions.id"))
    hire_date = db.Column(db.Date)
    is_active = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    created_at = db.Column(db.DateTime, nullable=False, default=now, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    department = db.relationship("Department")
    position = db.relationship("Position")
    issues = db.relationship("CardIssue", back_populates="employee", order_by="CardIssue.id.desc()")

    __table_args__ = (
        Index("idx_employees_name", "name"),
        Index("idx_employees_active", "is_active"),
    )

    def card_data(self, settings):
        """static/js/card.js의 frontSVG/backSVG가 받는 데이터 형식."""
        return {
            "name": self.name,
            "phone": format_phone(self.mobile),
            "nameEn": self.name_en or "",
            "dept": self.department.name if self.department else "",
            "title": self.position.name if self.position else "",
            "tel": format_phone(self.tel) if self.tel else "",
            "email": self.email or "",
            "company": settings["company_name"],
            "companyEn": settings["company_name_en"],
            "addr": settings["address"],
        }

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_en": self.name_en,
            "mobile": self.mobile,
            "tel": self.tel,
            "email": self.email,
            "department": self.department.name if self.department else None,
            "position": self.position.name if self.position else None,
            "hire_date": self.hire_date.isoformat() if self.hire_date else None,
            "is_active": self.is_active,
        }


class CardIssue(db.Model):
    __tablename__ = "card_issues"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    side = db.Column(db.Text, nullable=False)
    method = db.Column(db.Text, nullable=False)
    issued_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    snapshot_json = db.Column(db.Text)
    issued_at = db.Column(db.DateTime, default=now, server_default=func.current_timestamp())

    employee = db.relationship("Employee", back_populates="issues")
    user = db.relationship("User")

    __table_args__ = (
        CheckConstraint("side IN ('front','back','both')", name="ck_card_issues_side"),
        CheckConstraint("method IN ('png','print','zip')", name="ck_card_issues_method"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "side": self.side,
            "side_label": SIDE_LABELS.get(self.side, self.side),
            "method": self.method,
            "method_label": METHOD_LABELS.get(self.method, self.method),
            "issued_by": self.user.username if self.user else "",
            "issued_at": self.issued_at.strftime("%Y-%m-%d %H:%M") if self.issued_at else "",
        }


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.Text, primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now, server_default=func.current_timestamp())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.Text, nullable=False)
    target_id = db.Column(db.Integer)
    detail_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now, server_default=func.current_timestamp())


class BulkUpload(db.Model):
    """CSV 일괄 등록 미리보기 → 확정 사이에 업로드 내용을 보관한다.

    서버리스(Vercel)에서는 요청마다 다른 인스턴스가 처리할 수 있어 파일 대신 DB에 둔다.
    """
    __tablename__ = "bulk_uploads"
    token = db.Column(db.Text, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    rows_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)


def get_settings():
    values = dict(SETTING_DEFAULTS)
    for s in Setting.query.all():
        values[s.key] = s.value
    return values


def log_audit(user_id, action, target_id=None, detail=None):
    """F-16: 감사 로그. 커밋은 호출한 쪽에서 한다."""
    db.session.add(AuditLog(
        user_id=user_id,
        action=action,
        target_id=target_id,
        detail_json=json.dumps(detail, ensure_ascii=False, default=str) if detail is not None else None,
    ))
