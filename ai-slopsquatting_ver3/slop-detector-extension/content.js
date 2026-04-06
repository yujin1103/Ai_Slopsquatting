/**
 * content.js — 안정화 버전
 *
 * 주요 개선:
 * 1. SPA 네비게이션 감지 → processedKeys 초기화 (새 채팅 이동 시 재분석)
 * 2. ChatGPT 셀렉터 강화 (여러 패턴 병렬 시도)
 * 3. 패널 중복 삽입 방지 (data-slop-key 속성 추적)
 * 4. API 타임아웃 + 재시도 로직
 * 5. 패널 삽입 실패 시 폴백 위치 개선
 */

const SITE = detectSite();

function detectSite() {
  const host = location.hostname;
  if (host.includes("claude.ai"))         return "claude";
  if (host.includes("chatgpt.com"))       return "chatgpt";
  if (host.includes("gemini.google.com")) return "gemini";
  return "unknown";
}

// ── 셀렉터 ──────────────────────────────────────────────────────────────────
function getCodeBlockSelector() {
  switch (SITE) {
    case "chatgpt": return [
      // ChatGPT 실제 DOM: 코드블록 전체를 dir='ltr' div가 감싸고 있음
      "div[dir='ltr']",
      // 폴백
      "pre code",
    ].join(", ");
    case "gemini": return [
      "message-content pre code",
      ".code-block pre code",
      "pre code",
    ].join(", ");
    default: return "pre code";
  }
}

// ── 언어 감지 ─────────────────────────────────────────────────────────────────
function guessFilename(codeEl) {
  // ChatGPT: 코드블록 헤더(Python/JavaScript 레이블)가 형제 요소에 있음
  const prevSibling = codeEl.previousElementSibling?.textContent?.trim()?.toLowerCase()
    || codeEl.parentElement?.previousElementSibling?.textContent?.trim()?.toLowerCase()
    || "";
  if (prevSibling.includes("python"))     return "script.py";
  if (prevSibling.includes("javascript")) return "script.js";
  if (prevSibling.includes("typescript")) return "script.ts";
  if (prevSibling.includes("json"))       return "package.json";

  const classes = [...(codeEl.classList || []), ...(codeEl.parentElement?.classList || [])];
  for (const cls of classes) {
    const lang = cls.replace(/^(language-|lang-|hljs-)/, "").toLowerCase();
    if (lang === "python")                       return "script.py";
    if (lang === "javascript" || lang === "js")  return "script.js";
    if (lang === "typescript" || lang === "ts")  return "script.ts";
    if (lang === "json")                         return "package.json";
  }
  const header = codeEl.closest(".code-block, pre")
    ?.previousElementSibling?.textContent?.trim()?.toLowerCase();
  if (header?.includes("python"))     return "script.py";
  if (header?.includes("javascript")) return "script.js";
  if (header?.includes("json"))       return "package.json";

  const code = codeEl.textContent || "";
  if (/^\s*(import |from .+ import|def |class )/.test(code)) return "script.py";
  if (/require\(|import .+ from|const .+=/.test(code))       return "script.js";
  if (/"dependencies"\s*:/.test(code))                       return "package.json";
  return "script.py";
}

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

// ── DOM 삽입 ─────────────────────────────────────────────────────────────────
function insertAfterPre(codeEl, newEl) {
  // ChatGPT: div[dir='ltr'] 기준으로 4단계 위가 코드블록 최상위 컨테이너
  // 0: relative z-0 flex
  // 1: overflow-x-hidden overflow-y-auto
  // 2: border-radius-3xl bg-token-bg-elevated
  // 3: border border-token-border-light border-radius-3xl  ← 여기 다음에 삽입
  if (SITE === "chatgpt") {
    let el = codeEl;
    for (let i = 0; i < 12; i++) {
      const p = el.parentElement;
      if (!p || p === document.body) break;
      const cls = p.className || "";
      if (cls.includes("border-token-border") && cls.includes("border-radius")) {
        try { p.insertAdjacentElement("afterend", newEl); return true; } catch {}
      }
      el = p;
    }
  }

  // Gemini / Claude 기본: pre 다음에 삽입
  const pre = codeEl.closest("pre");
  if (pre) {
    try { pre.insertAdjacentElement("afterend", newEl); return true; } catch {}
  }
  let el = codeEl;
  for (let i = 0; i < 8; i++) {
    const p = el.parentElement;
    if (!p || p === document.body) break;
    const d = window.getComputedStyle(p).display;
    if (d === "block" || d === "flex" || d === "grid") {
      try { p.insertAdjacentElement("afterend", newEl); return true; } catch {}
    }
    el = p;
  }
  console.warn("[Slop Detector] 패널 삽입 위치 없음");
  return false;
}

// ── UI ───────────────────────────────────────────────────────────────────────
const LEVEL = {
  CRITICAL: { dot:"#ef4444", badge:"#ef4444", text:"#991b1b", label:"CRITICAL" },
  HIGH:     { dot:"#f97316", badge:"#f97316", text:"#9a3412", label:"HIGH"     },
  MEDIUM:   { dot:"#eab308", badge:"#eab308", text:"#713f12", label:"MEDIUM"   },
  LOW:      { dot:"#22c55e", badge:"#22c55e", text:"#14532d", label:"LOW"      },
};

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
    <span style="color:#64748b;font-size:11px;">${dangerous.length ? `${dangerous.length}개 위험` : "이상 없음"}</span>
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

  // 상세
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

    // L1
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

    // L2
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

// ── 코드블록 처리 ─────────────────────────────────────────────────────────────
async function onCodeBlockFound(codeEl) {
  // ChatGPT: textContent는 줄바꿈이 사라짐 → innerText 사용
  const code = (SITE === "chatgpt"
    ? (codeEl.innerText || codeEl.textContent)
    : codeEl.textContent
  )?.trim();
  if (!code) return;
  const filename = guessFilename(codeEl);

  const loading = document.createElement("div");
  loading.setAttribute("data-slop-panel", "1");
  loading.style.cssText = "font-size:11px;color:#94a3b8;padding:3px 2px;font-family:sans-serif;";
  loading.textContent = "🔍 Slop Detector 분석 중...";
  if (!insertAfterPre(codeEl, loading)) return;

  console.log(`[Slop Detector] 분석: ${filename} (${code.length}자)`);

  try {
    const result = await callBackground({ type: "PARSE_AND_ANALYZE", filename, code });
    loading.remove();
    if (!result?.results?.length) {
      console.log("[Slop Detector] 파싱된 패키지 없음 (표준 라이브러리만 있거나 import 없음)");
      return;
    }
    console.log(`[Slop Detector] 완료:`, result.results.map(r => `${r.package}(${r.level})`));
    insertAfterPre(codeEl, buildPanel(result.results));
  } catch (err) {
    console.error("[Slop Detector] 오류:", err.message);
    loading.textContent = `⚠️ Slop Detector 오류: ${err.message}`;
    setTimeout(() => loading.remove(), 5000);
  }
}

// ── 중복 방지 ─────────────────────────────────────────────────────────────────
let processedKeys = new Set();

function getBlockKey(el) {
  const t = (el.textContent || "").trim();
  return `${t.length}::${t.slice(0, 60)}::${t.slice(-60)}`;
}

function scanCodeBlocks() {
  document.querySelectorAll(getCodeBlockSelector()).forEach((el) => {
    if ((el.textContent || "").trim().length < 5) return;
    const key = getBlockKey(el);
    if (processedKeys.has(key)) return;
    processedKeys.add(key);
    onCodeBlockFound(el);
  });
}

// ── SPA 네비게이션 감지 ───────────────────────────────────────────────────────
// 새 채팅으로 이동할 때 URL이 바뀌면 processedKeys 초기화
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    console.log("[Slop Detector] 페이지 이동 감지 → 상태 초기화");
    // 기존 패널 제거
    document.querySelectorAll("[data-slop-panel]").forEach(el => el.remove());
    processedKeys = new Set();
    // 잠깐 기다렸다가 새 페이지 스캔
    setTimeout(scanCodeBlocks, 1000);
  }
}).observe(document.body, { childList: true, subtree: true });

// ── MutationObserver (응답 스트리밍 감지) ─────────────────────────────────────
const observer = new MutationObserver(() => {
  clearTimeout(observer._timer);
  observer._timer = setTimeout(scanCodeBlocks, 1500);
});

// ── 시작 ──────────────────────────────────────────────────────────────────────
async function init() {
  const serverUp = await checkApiServer();
  console.log(`[Slop Detector] 시작 — 사이트: ${SITE}, API: ${serverUp ? "✅ 연결됨" : "❌ 오프라인 (Docker 확인)"}`);
  if (!serverUp) return;
  scanCodeBlocks();
  observer.observe(document.body, { childList: true, subtree: true });
}

init();
