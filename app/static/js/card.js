/* 명함 SVG 생성 (원본 HTML에서 그대로 옮김, DOM 의존 없는 순수 함수)
 * frontSVG / backSVG 가 받는 데이터:
 *   {name, phone, nameEn, dept, title, tel, email, company, companyEn, addr}
 */
(function (global) {
  "use strict";

  const FONT = `'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif`;
  const C = { navy: "#0B2A5B", blue: "#0054A6", sky: "#00A0E2" };

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function fmtPhone(v) {
    const d = String(v ?? "").replace(/\D/g, "").slice(0, 11);
    if (d.startsWith("02")) {
      if (d.length <= 2) return d;
      if (d.length <= 5) return d.slice(0, 2) + "-" + d.slice(2);
      if (d.length <= 9) return d.slice(0, 2) + "-" + d.slice(2, d.length - 4) + "-" + d.slice(-4);
      return d.slice(0, 2) + "-" + d.slice(2, 6) + "-" + d.slice(6, 10);
    }
    if (d.length <= 3) return d;
    if (d.length <= 7) return d.slice(0, 3) + "-" + d.slice(3);
    if (d.length <= 10) return d.slice(0, 3) + "-" + d.slice(3, 6) + "-" + d.slice(6);
    return d.slice(0, 3) + "-" + d.slice(3, 7) + "-" + d.slice(7);
  }

  /* 원본 철도 모티프: 선로 + 진행선 (공식 로고 아님) */
  function railMotif(x, y, w, color, opacity = 1) {
    let ties = "";
    for (let i = 0; i < w; i += 22) ties += `<rect x="${x + i}" y="${y - 7}" width="4" height="18" fill="${color}" opacity="${.35 * opacity}"/>`;
    return `${ties}<rect x="${x}" y="${y - 3}" width="${w}" height="2.5" fill="${color}" opacity="${opacity}"/>
          <rect x="${x}" y="${y + 5}" width="${w}" height="2.5" fill="${color}" opacity="${opacity}"/>`;
  }

  function frontSVG(d) {
    const name = d.name || "홍길동";
    const phone = d.phone || "010-0000-0000";
    const nameSpaced = name.length <= 3 ? name.split("").join(" ") : name;
    const role = [d.dept, d.title].filter(Boolean).join("  |  ");
    const lines = [
      ["M", phone],
      d.tel ? ["T", d.tel] : null,
      d.email ? ["E", d.email] : null,
    ].filter(Boolean);
    let infoY = 330 - (lines.length - 1) * 19;
    const info = lines.map(([k, v], i) => `
    <text x="70" y="${infoY + i * 38}" font-size="19" font-weight="700" fill="${C.sky}">${k}</text>
    <text x="98" y="${infoY + i * 38}" font-size="21" fill="#1B2433" letter-spacing=".5">${esc(v)}</text>`).join("");
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" font-family="${FONT}">
  <rect width="900" height="500" fill="#FFFFFF"/>
  <!-- 좌측 컬러 바 -->
  <rect x="0" y="0" width="16" height="500" fill="${C.navy}"/>
  <rect x="16" y="0" width="6" height="500" fill="${C.sky}"/>
  <!-- 회사 표기 -->
  <text x="830" y="72" text-anchor="end" font-size="28" font-weight="800" fill="${C.blue}" letter-spacing="3">${esc(d.companyEn)}</text>
  <text x="830" y="100" text-anchor="end" font-size="15" fill="#5D6B82" letter-spacing="1">${esc(d.company)}</text>
  <!-- 이름 -->
  <text x="70" y="150" font-size="50" font-weight="800" fill="${C.navy}" letter-spacing="4">${esc(nameSpaced)}</text>
  ${d.nameEn ? `<text x="72" y="182" font-size="17" fill="#5D6B82" letter-spacing="1.5">${esc(d.nameEn)}</text>` : ""}
  ${role ? `<text x="72" y="${d.nameEn ? 218 : 192}" font-size="19" font-weight="600" fill="${C.blue}">${esc(role)}</text>` : ""}
  <rect x="70" y="252" width="56" height="3" fill="${C.sky}"/>
  ${info}
  <!-- 하단 선로 모티프 -->
  <rect x="22" y="430" width="878" height="70" fill="#F3F7FC"/>
  ${railMotif(22, 462, 878, C.blue, .85)}
  <text x="830" y="418" text-anchor="end" font-size="13.5" fill="#8593A8">${esc(d.addr)}</text>
</svg>`;
  }

  function backSVG(d) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500" font-family="${FONT}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${C.navy}"/><stop offset="1" stop-color="${C.blue}"/>
    </linearGradient>
  </defs>
  <rect width="900" height="500" fill="url(#g)"/>
  <!-- 곡선 노선 -->
  <path d="M-20 380 C 220 300, 420 430, 920 250" stroke="${C.sky}" stroke-width="5" fill="none" opacity=".9"/>
  <path d="M-20 410 C 240 330, 440 460, 920 285" stroke="#FFFFFF" stroke-width="2" fill="none" opacity=".35"/>
  <circle cx="300" cy="352" r="9" fill="#fff"/><circle cx="300" cy="352" r="4" fill="${C.sky}"/>
  <circle cx="620" cy="350" r="9" fill="#fff"/><circle cx="620" cy="350" r="4" fill="${C.sky}"/>
  <text x="450" y="200" text-anchor="middle" font-size="62" font-weight="800" fill="#FFFFFF" letter-spacing="10">${esc(d.companyEn)}</text>
  <text x="450" y="244" text-anchor="middle" font-size="21" fill="#CFE6F7" letter-spacing="6">${esc(d.company)}</text>
  ${railMotif(0, 474, 900, "#FFFFFF", .35)}
</svg>`;
  }

  /* SVG → Canvas → PNG (90×50mm @300dpi = 1063×591px). 성공하면 resolve. */
  function downloadPNG(svgStr, filename) {
    const W = 1063, H = 591;
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
        cv.getContext("2d").drawImage(img, 0, 0, W, H);
        cv.toBlob(b => {
          if (!b) return reject(new Error("PNG 변환에 실패했습니다."));
          const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = filename;
          document.body.appendChild(a); a.click(); a.remove();
          setTimeout(() => URL.revokeObjectURL(a.href), 1000);
          resolve({ width: W, height: H });
        }, "image/png");
      };
      img.onerror = () => reject(new Error("이미지 변환에 실패했습니다. 인쇄 기능을 이용해 주세요."));
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgStr);
    });
  }

  global.Card = { FONT, C, esc, fmtPhone, railMotif, frontSVG, backSVG, downloadPNG };
})(window);
