"""명함 렌더링 데이터와 발급 이력 JSON API."""
import json

from flask import Blueprint, jsonify, request
from flask_login import current_user

from ..extensions import db
from ..models import CardIssue, Employee, get_settings
from ..validators import MOBILE_RE, only_digits

bp = Blueprint("cards", __name__, url_prefix="/api")


def api_error(message, status):
    return jsonify(ok=False, error=message), status


@bp.get("/settings")
def settings():
    s = get_settings()
    return jsonify({k: s[k] for k in ("company_name", "company_name_en", "address", "email_domain")})


@bp.get("/employees/check-mobile")
def check_mobile():
    """F-04: 휴대전화 중복 확인."""
    mobile = only_digits(request.args.get("mobile"))
    if not MOBILE_RE.match(mobile):
        return api_error("휴대전화 번호를 정확히 입력해 주세요.", 400)
    q = Employee.query.filter(Employee.mobile == mobile)
    exclude_id = request.args.get("exclude_id", type=int)
    if exclude_id:
        q = q.filter(Employee.id != exclude_id)
    emp = q.first()
    if not emp:
        return jsonify(ok=True, exists=False)
    return jsonify(ok=True, exists=True, employee_id=emp.id, name=emp.name, is_active=bool(emp.is_active))


@bp.get("/employees/<int:id>/card")
def card(id):
    emp = db.session.get(Employee, id)
    if emp is None:
        return api_error("직원을 찾을 수 없습니다.", 404)
    return jsonify(ok=True, employee_id=emp.id, is_active=bool(emp.is_active),
                   card=emp.card_data(get_settings()))


@bp.post("/employees/<int:id>/issues")
def create_issue(id):
    """F-09: PNG 다운로드·인쇄 직전에 호출해 발급 이력을 남긴다."""
    emp = db.session.get(Employee, id)
    if emp is None:
        return api_error("직원을 찾을 수 없습니다.", 404)
    if not emp.is_active:
        return api_error("삭제된 직원의 명함은 발급할 수 없습니다.", 409)
    payload = request.get_json(silent=True) or {}
    side, method = payload.get("side"), payload.get("method")
    if side not in ("front", "back", "both"):
        return api_error("side 값이 올바르지 않습니다.", 400)
    if method not in ("png", "print", "zip"):
        return api_error("method 값이 올바르지 않습니다.", 400)
    issue = CardIssue(
        employee_id=emp.id,
        side=side,
        method=method,
        issued_by=current_user.id,
        snapshot_json=json.dumps(emp.card_data(get_settings()), ensure_ascii=False),
    )
    db.session.add(issue)
    db.session.commit()
    return jsonify(ok=True, issue_id=issue.id, issue=issue.to_dict()), 201
