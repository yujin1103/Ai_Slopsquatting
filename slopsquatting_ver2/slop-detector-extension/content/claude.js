/**
 * claude.js — claude.ai 전용
 *
 * 케이스 1: 코드블록 (pre code) → 즉시 감지
 * 케이스 2: 아티팩트 파일 카드 → 파일명·언어 표시 컴포넌트 감지
 */

// ── 언어 감지 ─────────────────────────────────────────────────────────────────
function guessFilename(codeEl) {
  const classes = [...(codeEl.classList || []), ...(codeEl.parentElement?.classList || [])];
  for (const cls of classes) {
    const lang = cls.replace(/^(language-|lang-)/, "").toLowerCase();
    if (lang === "python")                       return "script.py";
    if (lang === "javascript" || lang === "js")  return "script.js";
    if (lang === "typescript" || lang === "ts")  return "script.ts";
    if (lang === "json")                         return "package.json";
  }
  const code = codeEl.textContent || "";
  if (/^\s*(import |from .+ import|def |class )/.test(code)) return "script.py";
  if (/require\(|import .+ from/.test(code))                  return "script.js";
  if (/"dependencies"\s*:/.test(code))                        return "package.json";
  return "script.py";
}

// ── 코드블록 패널 삽입 ────────────────────────────────────────────────────────
function insertAfterCode(codeEl, newEl) {
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
  return false;
}

// ── 중복 방지 ─────────────────────────────────────────────────────────────────
let processedKeys = new Set();

function getKey(text) {
  return `${text.length}::${text.slice(0, 60)}::${text.slice(-60)}`;
}

// ── 케이스 1: 코드블록 스캔 ──────────────────────────────────────────────────
function scanCodeBlocks() {
  document.querySelectorAll("pre code").forEach(el => {
    const text = (el.textContent || "").trim();
    if (text.length < 80) return; // 짧은 스니펫 필터링
    const key = getKey(text);
    if (processedKeys.has(key)) return;
    processedKeys.add(key);

    // import 구문이 없으면 분석 불필요
    const hasImport = /^\s*(import |from .+ import)/m.test(text)
      || /require\(|"dependencies"/.test(text);
    if (!hasImport) return;

    const filename = guessFilename(el);
    analyzeAndRender(text, filename, (newEl) => insertAfterCode(el, newEl));
  });
}

// ── 케이스 2: 아티팩트 코드 에디터 감지 ────────────────────────────────────
// 아티팩트 뷰어의 코드는 top DOM에 token 요소로 렌더링됨
// token → 3단계 위 div.min-w-0.max-w-full 에 전체 코드가 있음

const processedArtifacts = new Set();

function extractArtifactCode() {
  const tokenEl = document.querySelector("[class*='token']");
  if (!tokenEl) return null;

  let el = tokenEl;
  for (let i = 0; i < 8; i++) {
    el = el.parentElement;
    if (!el) break;
    const cls = el.className || "";
    if (cls.includes("min-w-0") && cls.includes("max-w-full")) {
      // 줄번호 제거: "1\nimport numpy\n2\nimport pandas" → 짝수 줄만
      const raw = el.innerText || "";
      const lines = raw.split("\n");
      // 첫 번째가 숫자이면 줄번호가 있는 구조
      if (/^\d+$/.test(lines[0]?.trim())) {
        return lines.filter((_, i) => i % 2 === 1).join("\n");
      }
      return raw;
    }
  }
  return null;
}

function scanArtifacts() {
  const code = extractArtifactCode();
  if (!code || code.length < 80) return;

  const hasImport = /^\s*(import |from .+ import)/m.test(code)
    || /require\(|"dependencies"/.test(code);
  if (!hasImport) return;

  // 코드 내용 기반 중복 방지
  const key = `artifact::${code.length}::${code.slice(0, 60)}`;
  if (processedArtifacts.has(key)) return;
  processedArtifacts.add(key);

  const filename = /def |class |import pandas|import numpy/.test(code)
    ? "script.py" : "script.js";

  console.log(`[Slop Detector] 아티팩트 코드 감지: ${filename} (${code.length}자)`);

  // 삽입 위치: 아티팩트 카드 아래
  const card = document.querySelector(
    "[class*='artifact-block'], [class*='artifact-card'], [data-testid*='artifact']"
  );

  analyzeAndRender(code, filename, (newEl) => {
    if (card) {
      document.querySelectorAll("[data-slop-artifact-panel]").forEach(e => e.remove());
      newEl.setAttribute("data-slop-artifact-panel", "1");
      try { card.insertAdjacentElement("afterend", newEl); return true; } catch {}
    }
    return insertAfterCode(document.querySelector("[class*='token']"), newEl);
  });
}

// ── MutationObserver ──────────────────────────────────────────────────────────
const observer = new MutationObserver(() => {
  clearTimeout(observer._timer);
  observer._timer = setTimeout(() => {
    scanCodeBlocks();
    scanArtifacts();
  }, 1500);
});

// ── 시작 ──────────────────────────────────────────────────────────────────────
(async () => {
  const serverUp = await checkApiServer();
  console.log(`[Slop Detector] 시작 — 사이트: claude, API: ${serverUp ? "✅ 연결됨" : "❌ 오프라인"}`);
  if (!serverUp) return;

  watchNavigation(() => {
    processedKeys = new Set();
    processedArtifacts.clear();
    setTimeout(() => { scanCodeBlocks(); scanArtifacts(); }, 1000);
  });

  scanCodeBlocks();
  scanArtifacts();
  observer.observe(document.body, { childList: true, subtree: true });
})();

// ── 아티팩트 결과 수신 (postMessage from a.claude.ai iframe) ─────────────────
window.addEventListener("message", (event) => {
  if (event.origin !== "https://a.claude.ai") return;
  if (event.data?.type !== "SLOP_ARTIFACT_RESULT") return;

  const results = event.data.results;
  if (!results?.length) return;

  console.log(`[Slop Detector] 아티팩트 결과 수신:`, results.map(r => `${r.package}(${r.level})`));

  // 현재 열린 아티팩트 카드 찾기
  const artifactCard = document.querySelector(
    "[class*='artifact-block'], [class*='artifact-card'], [data-testid*='artifact']"
  );

  if (!artifactCard) {
    console.warn("[Slop Detector] 아티팩트 카드 DOM 없음");
    return;
  }

  // 기존 패널 제거 후 삽입
  document.querySelectorAll("[data-slop-artifact-panel]").forEach(el => el.remove());
  const panel = buildPanel(results);
  panel.setAttribute("data-slop-artifact-panel", "1");
  panel.style.margin = "4px 0 0";
  artifactCard.insertAdjacentElement("afterend", panel);
});
