from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Department, Employee, Position, get_settings, log_audit
from ..validators import format_phone, only_digits, validate_employee

bp = Blueprint("employees", __name__)


def active_choices(model, current_id=None):
    """활성 항목 + (수정 중인 직원이 쓰고 있는) 비활성 항목."""
    cond = model.is_active == 1
    if current_id:
        cond = or_(cond, model.id == current_id)
    return model.query.filter(cond).order_by(model.sort_order, model.id).all()


def parse_choice(form, field, model, current_id=None):
    """선택 상자 값 검증. (id 또는 None, 오류 메시지 또는 None)"""
    raw = (form.get(field) or "").strip()
    if not raw:
        return None, None
    try:
        obj = db.session.get(model, int(raw))
    except ValueError:
        obj = None
    if obj is None or (not obj.is_active and obj.id != current_id):
        return None, "목록에서 다시 선택해 주세요."
    return obj.id, None


def form_values(emp):
    return {
        "name": emp.name,
        "mobile": format_phone(emp.mobile),
        "name_en": emp.name_en or "",
        "department_id": str(emp.department_id or ""),
        "position_id": str(emp.position_id or ""),
        "tel": format_phone(emp.tel) if emp.tel else "",
        "email": emp.email or "",
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else "",
    }


def handle_form(emp=None):
    """등록/수정 공통 POST 처리. 성공하면 redirect, 실패하면 (템플릿, 상태코드)."""
    settings = get_settings()
    data, errors = validate_employee(request.form, settings["email_domain"])
    cur_dept = emp.department_id if emp else None
    cur_pos = emp.position_id if emp else None
    data["department_id"], err = parse_choice(request.form, "department_id", Department, cur_dept)
    if err:
        errors["department_id"] = err
    data["position_id"], err = parse_choice(request.form, "position_id", Position, cur_pos)
    if err:
        errors["position_id"] = err

    dup = None
    if "mobile" not in errors:
        q = Employee.query.filter(Employee.mobile == data["mobile"])
        if emp:
            q = q.filter(Employee.id != emp.id)
        dup = q.first()
        if dup:
            errors["mobile"] = "이미 등록된 휴대전화 번호입니다."

    if not errors:
        try:
            if emp is None:
                target = Employee(**data)
                db.session.add(target)
                db.session.flush()
                log_audit(current_user.id, "create", target.id, target.to_dict())
                msg = f"{target.name} 님을 등록했습니다. 명함을 저장하거나 인쇄할 수 있습니다."
            else:
                target = emp
                before = emp.to_dict()
                for k, v in data.items():
                    setattr(emp, k, v)
                db.session.flush()
                db.session.refresh(emp)
                after = emp.to_dict()
                changes = {k: [before[k], after[k]] for k in after if before[k] != after[k]}
                log_audit(current_user.id, "update", emp.id, changes)
                msg = f"{emp.name} 님 정보를 수정했습니다."
            db.session.commit()
            flash(msg, "success")
            return redirect(url_for("employees.detail", id=target.id))
        except IntegrityError:
            db.session.rollback()
            errors["mobile"] = "이미 등록된 휴대전화 번호입니다."
            dup = Employee.query.filter_by(mobile=data["mobile"]).first()

    status = 409 if dup else 400
    return render_form(emp, request.form.to_dict(), errors, dup), status


def render_form(emp, values, errors, dup=None):
    return render_template(
        "employees/form.html",
        employee=emp,
        values=values,
        errors=errors,
        dup=dup,
        departments=active_choices(Department, emp.department_id if emp else None),
        positions=active_choices(Position, emp.position_id if emp else None),
    )


@bp.route("/")
def index():
    return redirect(url_for("employees.list_"))


@bp.route("/employees")
def list_():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    query = Employee.query.outerjoin(Department).filter(Employee.is_active == 1)
    if q:
        conds = [Employee.name.contains(q, autoescape=True),
                 Department.name.contains(q, autoescape=True)]
        digits = only_digits(q)
        if digits:
            conds.append(Employee.mobile.contains(digits, autoescape=True))
        query = query.filter(or_(*conds))
    pagination = query.order_by(Employee.created_at.desc(), Employee.id.desc()).paginate(
        page=page, per_page=current_app.config["PER_PAGE"], error_out=False)
    return render_template("employees/list.html", pagination=pagination, q=q)


@bp.route("/employees/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        return handle_form()
    return render_form(None, {}, {})


@bp.route("/employees/<int:id>")
def detail(id):
    emp = db.session.get(Employee, id) or abort(404)
    return render_template("employees/detail.html", employee=emp, issues=emp.issues[:200])


@bp.route("/employees/<int:id>/edit", methods=["GET", "POST"])
def edit(id):
    emp = db.session.get(Employee, id) or abort(404)
    if not emp.is_active:
        flash("삭제된 직원은 복원한 뒤 수정할 수 있습니다.", "error")
        return redirect(url_for("employees.detail", id=id))
    if request.method == "POST":
        return handle_form(emp)
    return render_form(emp, form_values(emp), {})


@bp.route("/employees/<int:id>/delete", methods=["POST"])
def delete(id):
    emp = db.session.get(Employee, id) or abort(404)
    if emp.is_active:
        emp.is_active = 0
        log_audit(current_user.id, "delete", emp.id, {"name": emp.name})
        db.session.commit()
        flash(f"{emp.name} 님을 삭제 처리했습니다. (상세 화면에서 복원할 수 있습니다)", "info")
    return redirect(url_for("employees.list_"))


@bp.route("/employees/<int:id>/restore", methods=["POST"])
def restore(id):
    emp = db.session.get(Employee, id) or abort(404)
    if not emp.is_active:
        emp.is_active = 1
        log_audit(current_user.id, "update", emp.id, {"is_active": [0, 1]})
        db.session.commit()
        flash(f"{emp.name} 님을 복원했습니다.", "success")
    return redirect(url_for("employees.detail", id=id))
