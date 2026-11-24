/* 화면 동작: 입력 이벤트, 검증 표시, 미리보기 갱신, 버튼 핸들러 */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  /* ---------- 공통 ---------- */
  let toastTimer;
  function toast(msg) {
    const t = $("toast"); if (!t) return;
    t.textContent = msg; t.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
  }

  async function api(url, opts = {}) {
    const res = await fetch(url, {
      ...opts,
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, ...(opts.headers || {}) },
      credentials: "same-origin",
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok || body.ok === false) throw new Error(body.error || `요청에 실패했습니다. (${res.status})`);
    return body;
  }

  let currentView = "both";
  function setView(v) {
    currentView = v;
    document.querySelectorAll(".tabs button").forEach(b => b.classList.toggle("on", b.dataset.view === v));
    $("frontWrap").style.display = (v === "back") ? "none" : "";
    $("backWrap").style.display = (v === "front") ? "none" : "";
  }
  function setupTabs() {
    document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => setView(b.dataset.view)));
  }

  function companyFrom(stage) {
    return { company: stage.dataset.company || "", companyEn: stage.dataset.companyEn || "", addr: stage.dataset.addr || "" };
  }

  /* ---------- 검증 규칙 (app/validators.py와 같다) ---------- */
  const RULES = {
    name: v => { v = v.trim(); return !v ? "이름을 입력해 주세요." : v.length > 10 ? "이름은 10자 이내로 입력해 주세요." : ""; },
    mobile: v => /^01[016789]\d{7,8}$/.test(v.replace(/\D/g, "")) ? "" : "휴대전화 번호를 정확히 입력해 주세요.",
    tel: v => { const d = v.replace(/\D/g, ""); return !d || (d.length >= 9 && d.length <= 11) ? "" : "사무실 전화번호 형식이 올바르지 않습니다."; },
    email: v => { v = v.trim(); return !v || (v.length <= 100 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) ? "" : "이메일 형식이 올바르지 않습니다."; },
    name_en: v => { v = v.trim(); return !v || (v.length <= 40 && /^[A-Za-z \-]+$/.test(v) && /[A-Za-z]/.test(v)) ? "" : "영문 이름은 영문자만 입력해 주세요."; },
    hire_date: v => !v || /^\d{4}-\d{2}-\d{2}$/.test(v) ? "" : "입사일 형식이 올바르지 않습니다. (예: 2026-12-01)",
  };

  function setHint(field, msg) {
    const el = $(field), hint = $(field + "Hint");
    if (hint) hint.textContent = msg;
    if (el) el.classList.toggle("invalid", !!msg);
  }
  const check = field => { const msg = RULES[field]($(field).value); setHint(field, msg); return !msg; };

  /* ---------- 등록 / 수정 화면 ---------- */
  function initForm() {
    const form = $("empForm"); if (!form) return;
    const stage = $("stage");
    const co = companyFrom(stage);
    const domain = stage.dataset.emailDomain || "";
    const employeeId = form.dataset.employeeId || "";

    const optLabel = id => { const s = $(id); const o = s.options[s.selectedIndex]; return s.value && o ? (o.dataset.label || o.text) : ""; };
    const completeEmail = v => (v && !v.includes("@") && domain) ? `${v}@${domain}` : v;

    function data() {
      return {
        name: $("name").value.trim(),
        phone: $("mobile").value.trim(),
        nameEn: $("name_en").value.trim(),
        dept: optLabel("department_id"),
        title: optLabel("position_id"),
        tel: $("tel").value.trim(),
        email: completeEmail($("email").value.trim()),
        ...co,
      };
    }
    function render() {
      const d = data();
      $("frontWrap").innerHTML = Card.frontSVG(d);
      $("backWrap").innerHTML = Card.backSVG(d);
    }

    // 전화번호 자동 하이픈
    ["mobile", "tel"].forEach(id => $(id).addEventListener("input", e => { e.target.value = Card.fmtPhone(e.target.value); }));
    // 실시간 미리보기 (F-02)
    form.querySelectorAll("input,select").forEach(el => {
      el.addEventListener("input", render);
      el.addEventListener("change", render);
    });
    // 포커스를 벗어날 때 검증
    Object.keys(RULES).forEach(f => $(f).addEventListener("blur", () => { if ($(f).value || f === "name" || f === "mobile") check(f); }));
    // 이메일 자동 완성 (F-15)
    $("email").addEventListener("blur", () => { $("email").value = completeEmail($("email").value.trim()); check("email"); render(); });

    // 휴대전화 중복 확인 (F-04)
    const dupBox = $("mobileDup");
    let lastChecked = "";
    async function checkDup() {
      const digits = $("mobile").value.replace(/\D/g, "");
      if (RULES.mobile(digits) || digits === lastChecked) return;
      lastChecked = digits;
      try {
        const qs = new URLSearchParams({ mobile: digits });
        if (employeeId) qs.set("exclude_id", employeeId);
        const r = await api(`/api/employees/check-mobile?${qs}`);
        dupBox.textContent = "";
        if (r.exists) {
          dupBox.append("이미 등록된 번호입니다. ");
          const a = document.createElement("a");
          a.href = `/employees/${r.employee_id}`;
          a.textContent = `기존 직원 보기 (${r.name}${r.is_active ? "" : ", 삭제됨"}) →`;
          dupBox.append(a);
          $("mobile").classList.add("invalid");
        }
      } catch (e) { /* 중복 확인 실패는 저장 시 서버에서 다시 확인한다 */ }
    }
    $("mobile").addEventListener("blur", checkDup);
    $("mobile").addEventListener("input", () => { if (lastChecked) { lastChecked = ""; dupBox.textContent = ""; } });

    form.addEventListener("submit", e => {
      $("email").value = completeEmail($("email").value.trim());
      const ok = Object.keys(RULES).map(check).every(Boolean);
      if (!ok) {
        e.preventDefault();
        toast("입력 내용을 확인해 주세요.");
        const first = form.querySelector(".invalid"); if (first) first.focus();
        return;
      }
      const btn = $("saveBtn"); if (btn) { btn.disabled = true; btn.textContent = "저장 중…"; }
    });

    setupTabs();
    render();
    if (!employeeId && !$("name").value) $("name").focus();
  }

  /* ---------- 상세 화면: PNG 저장 / 인쇄 + 발급 이력 ---------- */
  function initDetail() {
    const stage = $("stage");
    if (!stage || !stage.dataset.employeeId) return;
    const id = stage.dataset.employeeId;
    let card = null;

    const ymd = () => { const n = new Date(); return `${n.getFullYear()}${String(n.getMonth() + 1).padStart(2, "0")}${String(n.getDate()).padStart(2, "0")}`; };

    function render() {
      $("frontWrap").innerHTML = Card.frontSVG(card);
      $("backWrap").innerHTML = Card.backSVG(card);
    }

    function addHistoryRow(issue) {
      const tbody = $("issueRows"); if (!tbody) return;
      const empty = $("issueEmpty"); if (empty) empty.remove();
      const tr = document.createElement("tr");
      [issue.issued_at, issue.side_label, issue.method_label, issue.issued_by].forEach(v => {
        const td = document.createElement("td"); td.textContent = v; tr.append(td);
      });
      tbody.prepend(tr);
      const cnt = $("issueCount"); if (cnt) cnt.textContent = String(Number(cnt.textContent || 0) + 1);
    }

    // 발급 직전에 이력을 남긴다 (F-09). 기록에 실패하면 발급하지 않는다.
    async function recordIssue(side, method) {
      const r = await api(`/api/employees/${id}/issues`, { method: "POST", body: JSON.stringify({ side, method }) });
      addHistoryRow(r.issue);
      return r;
    }

    async function withButton(btn, fn) {
      if (!card) return toast("명함 정보를 불러오는 중입니다.");
      btn.disabled = true;
      try { await fn(); }
      catch (e) { toast(e.message || "처리에 실패했습니다."); }
      finally { btn.disabled = false; }
    }

    const dlFront = $("dlFront"), dlBack = $("dlBack"), printBtn = $("print");
    if (dlFront) dlFront.addEventListener("click", () => withButton(dlFront, async () => {
      await recordIssue("front", "png");
      await Card.downloadPNG(Card.frontSVG(card), `명함_앞면_${card.name}_${ymd()}.png`);
      toast("앞면 PNG 파일을 저장했습니다.");
    }));
    if (dlBack) dlBack.addEventListener("click", () => withButton(dlBack, async () => {
      await recordIssue("back", "png");
      await Card.downloadPNG(Card.backSVG(card), `명함_뒷면_${card.name}_${ymd()}.png`);
      toast("뒷면 PNG 파일을 저장했습니다.");
    }));
    if (printBtn) printBtn.addEventListener("click", () => withButton(printBtn, async () => {
      await recordIssue("both", "print");
      const prev = currentView;
      setView("both");
      window.print();
      setView(prev);
    }));

    setupTabs();
    api(`/api/employees/${id}/card`)
      .then(r => { card = r.card; render(); })
      .catch(e => toast(e.message));
  }

  initForm();
  initDetail();
})();
