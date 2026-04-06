/**
 * common.js — 공통 유틸리티
 * claude.js / chatgpt.js / gemini.js 에서 공통으로 사용
 */

// ── 위험도 색상 ───────────────────────────────────────────────────────────────
const LEVEL = {
  CRITICAL: { dot:"#ef4444", badge:"#ef4444", text:"#991b1b", label:"CRITICAL" },
  HIGH:     { dot:"#f97316", badge:"#f97316", text:"#9a3412", label:"HIGH"     },
  MEDIUM:   { dot:"#eab308", badge:"#eab308", text:"#713f12", label:"MEDIUM"   },
  LOW:      { dot:"#22c55e", badge:"#22c55e", text:"#14532d", label:"LOW"      },
};

// ── background 통신 ──────────────────────────────────────────────────────────
function callBackground(message, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`타임아웃 (${timeoutMs / 1000}초 초과)`)),
      timeoutMs
    );
    chrome.runtime.sendMessage(message, (res) => {
      clearTimeout(timer);
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (res?.error) return reject(new Error(res.error));
      resolve(res);
    });
  });
}

async function checkApiServer() {
  try { return (await callBackground({ type: "HEALTH_CHECK" }, 3000))?.ok === true; }
  catch { return false; }
}

// ── 패널 생성 ─────────────────────────────────────────────────────────────────
function buildPanel(results) {
  const dangerous = results.filter(r => r.level !== "LOW");
  const worstLevel = dangerous.find(r => r.level === "CRITICAL") ? "CRITICAL"
    : dangerous.find(r => r.level === "HIGH")   ? "HIGH"
    : dangerous.find(r => r.level === "MEDIUM") ? "MEDIUM" : "LOW";
  const wc = LEVEL[worstLevel];

  const panel = document.createElement("div");
  panel.setAttribute("data-slop-panel", "1");
  panel.style.cssText = `
    margin:4px 0 6px;
    border:1px solid ${dangerous.length ? wc.dot + "55" : "#d1fae5"};
    border-radius:6px; overflow:hidden;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    font-size:12px; background:#fff;
  `;

  // 요약 행
  const summary = document.createElement("div");
  summary.style.cssText = `
    display:flex; align-items:center; gap:6px; padding:5px 10px;
    background:${dangerous.length ? wc.dot + "18" : "#f0fdf4"};
    cursor:pointer; user-select:none;
  `;
  summary.innerHTML = `
    <span style="font-size:12px;">${dangerous.length ? "⚠️" : "✅"}</span>
    <b style="color:#1e293b;font-size:12px;">Slop Detector</b>
    <span style="color:#64748b;font-size:11px;">
      ${dangerous.length ? `${dangerous.length}개 위험` : "이상 없음"}
    </span>
    <span style="display:flex;gap:3px;flex-wrap:wrap;flex:1;">
      ${results.map(r => {
        const c = LEVEL[r.level];
        return `<span style="
          display:inline-flex;align-items:center;gap:3px;
          padding:1px 6px;border-radius:99px;font-size:10px;
          background:${c.dot}22;color:${c.text};
          border:1px solid ${c.dot}44;font-family:monospace;
        "><span style="width:5px;height:5px;border-radius:50%;background:${c.dot};display:inline-block;"></span>${r.package}</span>`;
      }).join("")}
    </span>
    <span class="slop-toggle" style="color:#94a3b8;font-size:11px;flex-shrink:0;">▸ 상세</span>
  `;
  panel.appendChild(summary);

  // 상세 영역
  const detail = document.createElement("div");
  detail.style.cssText = "display:none;border-top:1px solid #f1f5f9;";

  results.forEach(r => {
    const c = LEVEL[r.level];
    const metaSignals = (r.signals || []).filter(s => !s.includes("[소스]"));
    const srcSignals  = (r.signals || []).filter(s =>  s.includes("[소스]"));
    const hasSrc = srcSignals.length > 0;

    const row = document.createElement("div");
    row.style.cssText = "padding:7px 10px;border-bottom:1px solid #f8fafc;";
    row.innerHTML = `
      <div style="display:flex;align-items:center;gap:5px;margin-bottom:4px;">
        <span style="width:7px;height:7px;border-radius:50%;background:${c.dot};display:inline-block;"></span>
        <b style="font-family:monospace;color:#1e293b;">${r.package}</b>
        <span style="padding:1px 6px;border-radius:99px;font-size:10px;font-weight:700;background:${c.badge};color:#fff;">${c.label}</span>
        <span style="color:#94a3b8;font-size:10px;">점수 ${r.score}/100</span>
      </div>
    `;

    // Layer 1: 메타데이터
    const L1 = document.createElement("div");
    L1.style.cssText = `margin:0 0 3px 12px;padding:4px 7px;background:#f8fafc;border-left:2px solid #94a3b8;border-radius:0 3px 3px 0;font-size:11px;`;
    L1.innerHTML = `
      <b style="color:#475569;">L1 메타데이터</b>
      <span style="color:#94a3b8;">
        ${r.reg_days   != null ? ` · ${r.reg_days}일` : ""}
        ${r.version_count      ? ` · v${r.version_count}개` : ""}
        · ${r.metadata_score ?? 0}점
      </span><br>
      ${metaSignals.map(s => `<span style="color:#475569;">${s}</span>`).join("<br>") || ""}
    `;
    row.appendChild(L1);

    // Layer 2: 소스 분석
    const L2 = document.createElement("div");
    L2.style.cssText = `margin:0 0 0 12px;padding:4px 7px;background:${hasSrc ? "#fff7ed" : "#f0fdf4"};border-left:2px solid ${hasSrc ? "#f97316" : "#22c55e"};border-radius:0 3px 3px 0;font-size:11px;`;
    if (r.source_analyzed) {
      L2.innerHTML = `
        <b style="color:#475569;">L2 소스 분석</b>
        <span style="color:#94a3b8;"> · ${r.source_score ?? 0}점</span><br>
        ${hasSrc
          ? srcSignals.map(s => `<span style="color:#9a3412;">${s}</span>`).join("<br>")
          : `<span style="color:#15803d;">✅ 악성 패턴 없음</span>`}
      `;
    } else if (r.pypi_exists || r.npm_exists) {
      L2.innerHTML = `<span style="color:#94a3b8;">L2 소스 분석 스킵 (아카이브 5MB 초과)</span>`;
    } else {
      L2.innerHTML = `<span style="color:#94a3b8;">L2 미등록 패키지 — 소스 분석 불가</span>`;
    }
    row.appendChild(L2);
    detail.appendChild(row);
  });

  panel.appendChild(detail);

  // 토글
  let open = dangerous.length > 0;
  detail.style.display = open ? "block" : "none";
  summary.querySelector(".slop-toggle").textContent = open ? "▾ 닫기" : "▸ 상세";
  summary.addEventListener("click", () => {
    open = !open;
    detail.style.display = open ? "block" : "none";
    summary.querySelector(".slop-toggle").textContent = open ? "▾ 닫기" : "▸ 상세";
  });

  return panel;
}

// ── 공통 분석 실행 ─────────────────────────────────────────────────────────────
async function analyzeAndRender(code, filename, insertFn) {
  const loading = document.createElement("div");
  loading.setAttribute("data-slop-panel", "1");
  loading.style.cssText = "font-size:11px;color:#94a3b8;padding:3px 2px;font-family:sans-serif;";
  loading.textContent = "🔍 Slop Detector 분석 중...";

  if (!insertFn(loading)) return;

  console.log(`[Slop Detector] 분석: ${filename} (${code.length}자)`);

  try {
    const result = await callBackground({ type: "PARSE_AND_ANALYZE", filename, code });
    loading.remove();
    if (!result?.results?.length) {
      return;
    }
    console.log(`[Slop Detector] 완료:`, result.results.map(r => `${r.package}(${r.level})`));
    insertFn(buildPanel(result.results));
  } catch (err) {
    console.error("[Slop Detector] 오류:", err.message);
    loading.textContent = `⚠️ Slop Detector 오류: ${err.message}`;
    setTimeout(() => loading.remove(), 5000);
  }
}

// ── SPA 네비게이션 감지 ───────────────────────────────────────────────────────
function watchNavigation(onNavigate) {
  let lastUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      console.log("[Slop Detector] 페이지 이동 감지 → 상태 초기화");
      document.querySelectorAll("[data-slop-panel]").forEach(el => el.remove());
      onNavigate();
    }
  }).observe(document.body, { childList: true, subtree: true });
}
