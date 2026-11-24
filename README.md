# 신규 직원 명함 자동 제작 웹앱 (Flask + SQLite)

이름·휴대전화를 입력하면 명함(앞·뒷면, 90×50mm)이 자동으로 만들어지고, 직원 정보와 발급 이력이 DB에 저장됩니다.
원본 단일 HTML(`../신규 직원 명함 자동 제작.html`)의 디자인과 SVG 생성 코드를 그대로 옮겼습니다.

## 실행 순서

Python 3.11 이상이 필요합니다.

```bash
# 1) 가상환경
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2) 패키지 설치
pip install -r requirements.txt

# 3) 환경변수
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
# → .env의 SECRET_KEY를 임의의 긴 문자열로 바꾼다
#   (예: python -c "import secrets; print(secrets.token_hex(32))")

# 4) DB 초기화 + 관리자 생성
flask --app run init-db
flask --app run create-admin

# 5) 실행
flask --app run run --debug
# → http://127.0.0.1:5000 접속
```

> Windows에서 `python` 명령이 없으면 `py -3.12 -m venv .venv`처럼 `py` 런처를 쓰세요.
> 같은 네트워크의 다른 PC에서 접속해야 할 때만 `flask --app run run --host 0.0.0.0`을 씁니다.

## 배포 (GitHub + Vercel + Supabase)

| 구성 | 이름 |
|---|---|
| GitHub 저장소 | `261124_KORAIL` |
| Supabase 프로젝트 | `261124_KORAIL` (서울 `ap-northeast-2`) |
| Vercel 프로젝트 | `261124_korail` (Vercel 이름 규칙상 소문자) |

- Vercel은 `index.py`의 `app`을 Python 서버리스 함수로 실행합니다.
- DB는 Supabase Postgres(트랜잭션 풀러, 6543 포트)를 씁니다. 드라이버는 순수 Python인 `pg8000`입니다.
- Vercel 환경변수: `DATABASE_URL`(Supabase 연결 문자열), `SECRET_KEY`.
- Supabase 테이블은 모두 RLS를 켜 두어 Supabase Data API(anon 키)로는 읽거나 쓸 수 없습니다. 앱은 DB에 직접 접속하므로 영향이 없습니다.

Supabase DB에 테이블을 만들거나 관리자 비밀번호를 바꿀 때는 `DATABASE_URL`을 Supabase 주소로 지정하고 같은 명령을 씁니다.

```powershell
$env:DATABASE_URL = "postgresql://postgres.<프로젝트ref>:<DB비밀번호>@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
flask --app run init-db
flask --app run create-admin
Remove-Item Env:DATABASE_URL
```

## 테스트

```bash
pytest -q
```

메모리 SQLite(`TestConfig`)로 실행되며 실제 `instance/card.db`는 건드리지 않습니다.

## 기능

| 번호 | 기능 | 위치 |
|---|---|---|
| F-01·02 | 직원 등록 + 실시간 미리보기 | 직원 등록 |
| F-03 | 서버 측 입력 검증 (`app/validators.py`) | 저장 시 필드 아래에 표시 |
| F-04 | 휴대전화 중복 확인 (입력 중 + 저장 시 409) | 직원 등록·수정 |
| F-05 | 이름·부서·전화번호 검색, 20건씩 페이지 | 직원 목록 |
| F-06 | 수정, 삭제 표시(`is_active=0`)·복원 | 직원 상세 |
| F-07·08·09 | PNG 저장(1063×591, `명함_앞면_{이름}_{YYYYMMDD}.png`), 인쇄, 발급 이력 | 직원 상세 |
| F-10·11 | 회사 정보, 부서·직급 추가·순서·사용 중지 | 관리 설정 |
| F-12 | 관리자 로그인 (비밀번호 해시 저장) | 모든 화면 |
| F-13 | CSV 일괄 등록 (UTF-8/CP949, 최대 500행) | CSV 일괄 등록 |
| F-15 | 이메일 아이디만 입력하면 도메인 자동 완성 | 직원 등록·수정, CSV |
| F-16 | 등록·수정·삭제·일괄 등록 감사 로그(`audit_logs`) | DB |

F-14(ZIP 일괄 PNG)는 2단계 범위입니다 (서버 측 `cairosvg` 렌더링 필요).

## 폴더 구조

```
app/            Flask 앱 (앱 팩토리, 모델, 검증, 화면·API)
app/static/js/  card.js(명함 SVG·PNG, 원본에서 이전) · form.js(화면 동작)
instance/       card.db (자동 생성, 저장소에 넣지 않음)
scripts/        sample_employees.csv (CSV 일괄 등록 샘플: 정상·중복·오류 행 포함)
tests/          pytest
```

## 참고

- `instance/card.db`에는 직원 전화번호·이메일(개인정보)이 들어 있습니다. 백업 파일을 외부에 공유하지 마세요.
- 초기 부서 목록(경영기획본부 등)은 예시입니다. 관리 설정에서 실제 조직에 맞게 바꾸세요.
- 공식 CI 로고는 포함하지 않았습니다. 승인된 로고를 받으면 `app/static/img/`에 넣고 `card.js`의 앞면 회사 표기 영역을 교체하세요.
- 회사 PC에서 `DLL load failed … 애플리케이션 제어 정책` 오류가 나면 `requirements.txt`대로 SQLAlchemy 2.0.x가 설치되었는지 확인하세요 (2.1은 순수 Python으로 대체 실행되지 않습니다).
