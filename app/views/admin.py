"""F-10 회사 정보 설정, F-11 부서·직급 관리."""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Department, Position, Setting, get_settings

bp = Blueprint("admin", __name__, url_prefix="/admin")

KINDS = {"dept": (Department, "부서"), "pos": (Position, "직급")}
DOMAIN_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
SETTING_FIELDS = [
    ("company_name", "회사명"),
    ("company_name_en", "회사 영문명"),
    ("address", "주소"),
    ("email_domain", "이메일 도메인"),
]


def _save_settings(form):
    values, errors = {}, {}
    for key, label in SETTING_FIELDS:
        v = (form.get(key) or "").strip()
        if not v:
            errors[key] = f"{label}을(를) 입력해 주세요."
        elif len(v) > 100:
            errors[key] = f"{label}은(는) 100자 이내로 입력해 주세요."
        values[key] = v
    if "email_domain" not in errors:
        values["email_domain"] = values["email_domain"].lstrip("@")
        if not DOMAIN_RE.match(values["email_domain"]):
            errors["email_domain"] = "도메인 형식이 올바르지 않습니다. (예: korail.com)"
    if errors:
        return errors
    for key, v in values.items():
        row = db.session.get(Setting, key)
        if row:
            row.value = v
        else:
            db.session.add(Setting(key=key, value=v))
    db.session.commit()
    return None


def _ordered(model):
    return model.query.order_by(model.sort_order, model.id).all()


def _handle_list_action(action, form):
    kind = form.get("kind")
    if kind not in KINDS:
        flash("잘못된 요청입니다.", "error")
        return
    model, label = KINDS[kind]

    if action == "add":
        name = (form.get("name") or "").strip()
        if not name or len(name) > 30:
            flash(f"{label} 이름은 1~30자로 입력해 주세요.", "error")
            return
        if model.query.filter_by(name=name).first():
            flash(f"이미 있는 {label}입니다: {name}", "error")
            return
        last = model.query.order_by(model.sort_order.desc()).first()
        db.session.add(model(name=name, sort_order=(last.sort_order + 1) if last else 0))
        db.session.commit()
        flash(f"{label} '{name}'을(를) 추가했습니다.", "success")
        return

    obj = db.session.get(model, form.get("id", type=int) or 0)
    if obj is None:
        flash("대상을 찾을 수 없습니다.", "error")
        return

    if action == "toggle":
        obj.is_active = 0 if obj.is_active else 1
        db.session.commit()
        state = "사용" if obj.is_active else "사용 중지"
        flash(f"{label} '{obj.name}'을(를) {state}로 바꿨습니다.", "success")
    elif action in ("up", "down"):
        items = _ordered(model)
        for i, it in enumerate(items):
            it.sort_order = i
        idx = items.index(obj)
        swap = idx - 1 if action == "up" else idx + 1
        if 0 <= swap < len(items):
            items[idx].sort_order, items[swap].sort_order = items[swap].sort_order, items[idx].sort_order
        db.session.commit()


@bp.route("/settings", methods=["GET", "POST"])
def settings_page():
    errors = {}
    values = get_settings()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "settings":
            errors = _save_settings(request.form) or {}
            if not errors:
                flash("회사 정보를 저장했습니다. 모든 명함에 바로 반영됩니다.", "success")
                return redirect(url_for("admin.settings_page"))
            values = request.form.to_dict()
        else:
            _handle_list_action(action, request.form)
            return redirect(url_for("admin.settings_page") + "#lists")
    return render_template(
        "admin/settings.html",
        values=values,
        errors=errors,
        fields=SETTING_FIELDS,
        departments=_ordered(Department),
        positions=_ordered(Position),
    ), (400 if errors else 200)
