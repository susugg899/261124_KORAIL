import io
import json

from app.extensions import db
from app.models import AuditLog, CardIssue, Department, Employee, Position, Setting


def _create(client, **kw):
    data = {"name": "홍길동", "mobile": "010-1234-5678"}
    data.update(kw)
    return client.post("/employees/new", data=data)


def test_login_required_redirects(anon):
    res = anon.get("/employees")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_login_required_api_returns_json(anon):
    res = anon.get("/api/settings")
    assert res.status_code == 401
    assert res.get_json()["ok"] is False


def test_wrong_password(anon):
    res = anon.post("/login", data={"username": "admin", "password": "nope"})
    assert res.status_code == 401
    assert "올바르지 않습니다" in res.get_data(as_text=True)


def test_crud_flow(client, app):
    # 등록 (이름·휴대전화만)
    res = _create(client)
    assert res.status_code == 302
    emp = Employee.query.filter_by(mobile="01012345678").one()
    assert emp.is_active == 1

    # 목록에 표시
    html = client.get("/employees").get_data(as_text=True)
    assert "홍길동" in html and "010-1234-5678" in html

    # 수정
    dept = Department.query.filter_by(name="여객사업본부").one()
    pos = Position.query.filter_by(name="대리").one()
    res = client.post(f"/employees/{emp.id}/edit", data={
        "name": "홍길순", "mobile": "010-1234-5678", "department_id": dept.id,
        "position_id": pos.id, "email": "gilsun",
    })
    assert res.status_code == 302
    db.session.refresh(emp)
    assert emp.name == "홍길순"
    assert emp.email == "gilsun@korail.com"  # F-15 자동 완성
    card = client.get(f"/api/employees/{emp.id}/card").get_json()["card"]
    assert card["dept"] == "여객사업본부" and card["title"] == "대리" and card["phone"] == "010-1234-5678"

    # 삭제 표시 → 목록에서 사라짐, DB에는 남음
    res = client.post(f"/employees/{emp.id}/delete")
    assert res.status_code == 302
    db.session.refresh(emp)
    assert emp.is_active == 0
    assert f'href="/employees/{emp.id}">' not in client.get("/employees").get_data(as_text=True)

    actions = [a.action for a in AuditLog.query.order_by(AuditLog.id)]
    assert actions == ["create", "update", "delete"]


def test_duplicate_mobile_returns_409(client):
    assert _create(client).status_code == 302
    res = _create(client, name="김철수", mobile="01012345678")
    assert res.status_code == 409
    assert "이미 등록된 휴대전화 번호" in res.get_data(as_text=True)
    assert Employee.query.count() == 1


def test_check_mobile_api(client):
    _create(client)
    emp = Employee.query.one()
    r = client.get("/api/employees/check-mobile?mobile=010-1234-5678").get_json()
    assert r["exists"] is True and r["employee_id"] == emp.id
    r = client.get(f"/api/employees/check-mobile?mobile=01012345678&exclude_id={emp.id}").get_json()
    assert r["exists"] is False
    assert client.get("/api/employees/check-mobile?mobile=123").status_code == 400


def test_server_validation(client):
    res = _create(client, name="", mobile="010-12", email="a@b", name_en="홍")
    assert res.status_code == 400
    html = res.get_data(as_text=True)
    for msg in ("이름을 입력해 주세요.", "휴대전화 번호를 정확히 입력해 주세요.",
                "이메일 형식이 올바르지 않습니다.", "영문 이름은 영문자만 입력해 주세요."):
        assert msg in html
    assert Employee.query.count() == 0


def test_issue_api_adds_record(client):
    _create(client)
    emp = Employee.query.one()
    res = client.post(f"/api/employees/{emp.id}/issues", json={"side": "front", "method": "png"})
    assert res.status_code == 201
    body = res.get_json()
    assert body["ok"] is True and body["issue_id"]
    assert CardIssue.query.count() == 1
    issue = CardIssue.query.one()
    assert json.loads(issue.snapshot_json)["name"] == "홍길동"
    # 잘못된 값 / 없는 직원
    assert client.post(f"/api/employees/{emp.id}/issues", json={"side": "x", "method": "png"}).status_code == 400
    assert client.post("/api/employees/999/issues", json={"side": "front", "method": "png"}).status_code == 404
    assert CardIssue.query.count() == 1


def test_search_and_pagination(client):
    for i in range(25):
        _create(client, name=f"직원{i:02d}", mobile=f"010-1000-{i:04d}")
    html = client.get("/employees").get_data(as_text=True)
    assert "총 25명" in html and html.count('href="/employees/') >= 20
    html2 = client.get("/employees?page=2").get_data(as_text=True)
    assert "직원00" in html2  # 최신순이므로 처음 등록한 직원은 2페이지
    html3 = client.get("/employees?q=10000024").get_data(as_text=True)
    assert "총 1명" in html3 and "직원24" in html3


def test_settings_change_reflects_in_card(client):
    _create(client)
    emp = Employee.query.one()
    res = client.post("/admin/settings", data={
        "action": "settings", "company_name": "테스트공사", "company_name_en": "TEST",
        "address": "서울", "email_domain": "test.com",
    })
    assert res.status_code == 302
    assert db.session.get(Setting, "company_name").value == "테스트공사"
    card = client.get(f"/api/employees/{emp.id}/card").get_json()["card"]
    assert card["company"] == "테스트공사" and card["companyEn"] == "TEST"


def test_department_admin(client):
    client.post("/admin/settings", data={"action": "add", "kind": "dept", "name": "신설본부"})
    d = Department.query.filter_by(name="신설본부").one()
    client.post("/admin/settings", data={"action": "toggle", "kind": "dept", "id": d.id})
    db.session.refresh(d)
    assert d.is_active == 0
    # 비활성 부서는 새 등록에 쓸 수 없다
    res = _create(client, department_id=d.id)
    assert res.status_code == 400


def test_bulk_upload(client):
    csv_text = (
        "name,mobile,name_en,department,position,tel,email,hire_date\n"
        "홍길동,010-1234-5678,Hong Gil-dong,여객사업본부,대리,042-000-0000,gildong,2026-12-01\n"
        "박민수,010-1234-5678,,,,,,\n"          # 파일 내 중복
        ",010-4567-8901,,,,,,\n"                 # 이름 없음
        "최지우,010-5678-9012,,없는본부,,,,\n"   # 없는 부서
    )
    raw = csv_text.encode("cp949")
    res = client.post("/bulk/upload", data={"file": (io.BytesIO(raw), "list.csv")},
                      content_type="multipart/form-data")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "CP949" in html and "정상 1" in html and "오류 2" in html and "중복 1" in html
    token = html.split('name="token" value="')[1].split('"')[0]
    res = client.post("/bulk/confirm", data={"token": token})
    assert res.status_code == 302
    emp = Employee.query.one()
    assert emp.name == "홍길동" and emp.email == "gildong@korail.com"
    assert AuditLog.query.filter_by(action="bulk_import").count() == 1
