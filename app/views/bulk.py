"""F-13: CSV 일괄 등록 (업로드 → 행별 검증 → 정상 행만 저장)."""
import csv
import io
import json
import os
import re
import secrets
from datetime import timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template, request, send_file,
                   url_for)
from flask_login import current_user

from ..extensions import db
from ..models import BulkUpload, Department, Employee, Position, get_settings, log_audit, now
from ..validators import validate_employee

bp = Blueprint("bulk", __name__, url_prefix="/bulk")

MAX_ROWS = 500
COLUMNS = ["name", "mobile", "name_en", "department", "position", "tel", "email", "hire_date"]
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
TMP_TTL = timedelta(hours=24)


def _cleanup_tmp():
    BulkUpload.query.filter(BulkUpload.created_at < now() - TMP_TTL).delete()


def decode_csv(raw):
    """UTF-8(BOM 포함)을 먼저 시도하고, 실패하면 CP949로 읽는다."""
    try:
        return raw.decode("utf-8-sig"), "UTF-8"
    except UnicodeDecodeError:
        return raw.decode("cp949"), "CP949"


def read_rows(text):
    reader = csv.DictReader(io.StringIO(text))
    headers = [(h or "").strip() for h in (reader.fieldnames or [])]
    missing = [c for c in ("name", "mobile") if c not in headers]
    if missing:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing)} (첫 줄은 {','.join(COLUMNS)} 형식이어야 합니다)")
    reader.fieldnames = headers
    rows = []
    for r in reader:
        if not any((v or "").strip() for v in r.values() if isinstance(v, str)):
            continue  # 빈 줄
        rows.append({c: (r.get(c) or "").strip() for c in COLUMNS})
        if len(rows) > MAX_ROWS:
            raise ValueError(f"최대 {MAX_ROWS}행까지 올릴 수 있습니다.")
    return rows


def evaluate(rows):
    """행별 검증. status: ok / error / dup"""
    domain = get_settings()["email_domain"]
    depts = {d.name: d.id for d in Department.query.filter_by(is_active=1)}
    poss = {p.name: p.id for p in Position.query.filter_by(is_active=1)}
    existing = {m for (m,) in db.session.query(Employee.mobile)}
    seen = set()
    result = []
    for i, r in enumerate(rows, start=2):  # 1행은 머리글
        data, errors = validate_employee(r, domain)
        msgs = list(errors.values())
        data["department_id"] = data["position_id"] = None
        if r["department"]:
            if r["department"] in depts:
                data["department_id"] = depts[r["department"]]
            else:
                msgs.append(f"등록되지 않은 부서입니다: {r['department']}")
        if r["position"]:
            if r["position"] in poss:
                data["position_id"] = poss[r["position"]]
            else:
                msgs.append(f"등록되지 않은 직급입니다: {r['position']}")
        status = "error" if msgs else "ok"
        if "mobile" not in errors:
            if data["mobile"] in existing:
                status, msgs = "dup", msgs + ["이미 등록된 휴대전화 번호입니다."]
            elif data["mobile"] in seen:
                status, msgs = "dup", msgs + ["파일 안에서 휴대전화 번호가 중복됩니다."]
            seen.add(data["mobile"])
        result.append({"line": i, "raw": r, "status": status, "messages": msgs, "data": data})
    return result


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("bulk/upload.html", result=None)
    f = request.files.get("file")
    if not f or not f.filename:
        flash("CSV 파일을 선택해 주세요.", "error")
        return redirect(url_for("bulk.upload"))
    try:
        text, encoding = decode_csv(f.read())
        rows = read_rows(text)
    except (UnicodeDecodeError, ValueError, csv.Error) as e:
        msg = str(e) if isinstance(e, ValueError) else "CSV 파일을 읽을 수 없습니다. 인코딩(UTF-8/CP949)과 형식을 확인해 주세요."
        flash(msg, "error")
        return redirect(url_for("bulk.upload"))
    if not rows:
        flash("등록할 행이 없습니다.", "error")
        return redirect(url_for("bulk.upload"))

    _cleanup_tmp()
    token = secrets.token_urlsafe(24)
    db.session.add(BulkUpload(token=token, user_id=current_user.id,
                              rows_json=json.dumps(rows, ensure_ascii=False)))
    db.session.commit()
    result = evaluate(rows)
    counts = {s: sum(1 for r in result if r["status"] == s) for s in ("ok", "error", "dup")}
    return render_template("bulk/upload.html", result=result, counts=counts, token=token,
                           filename=f.filename, encoding=encoding)


@bp.route("/confirm", methods=["POST"])
def confirm():
    token = request.form.get("token") or ""
    pending = db.session.get(BulkUpload, token) if TOKEN_RE.match(token) else None
    if pending is None or pending.created_at < now() - TMP_TTL:
        flash("업로드 정보가 만료되었습니다. 파일을 다시 올려 주세요.", "error")
        return redirect(url_for("bulk.upload"))
    rows = json.loads(pending.rows_json)
    db.session.delete(pending)

    # 미리보기 이후 DB가 바뀌었을 수 있으므로 다시 검증한다.
    result = evaluate(rows)
    created = []
    for r in result:
        if r["status"] == "ok":
            emp = Employee(**r["data"])
            db.session.add(emp)
            db.session.flush()
            created.append(emp.id)
    skipped = len(result) - len(created)
    if created:
        log_audit(current_user.id, "bulk_import", None, {"count": len(created), "employee_ids": created})
    db.session.commit()
    flash(f"{len(created)}명을 등록했습니다." + (f" (오류·중복 {skipped}행 제외)" if skipped else ""), "success")
    return redirect(url_for("employees.list_"))


@bp.route("/sample.csv")
def sample():
    path = os.path.join(os.path.dirname(current_app.root_path), "scripts", "sample_employees.csv")
    return send_file(path, mimetype="text/csv", as_attachment=True, download_name="sample_employees.csv")
