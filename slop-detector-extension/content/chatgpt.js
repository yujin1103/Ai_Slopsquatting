/**
 * chatgpt.js — chatgpt.com 전용
 *
 * ChatGPT DOM 특성:
 * - 코드블록: pre 없이 div[dir='ltr'] 가 전체 코드를 담음
 * - 언어 레이블: 코드블록 이전 형제 요소에 "Python" 등 텍스트
 * - textContent 사용 시 줄바꿈 사라짐 → innerText 사용
 * - 삽입 위치: border-token-border-light 컨테이너 다음
 */

// ── 언어 감지 ─────────────────────────────────────────────────────────────────
function guessFilename(codeEl) {
  // ChatGPT: 코드블록 헤더가 이전 형제 요소에 있음
  const prevSibling =
    codeEl.previousElementSibling?.textContent?.trim()?.toLowerCase() ||
    codeEl.parentElement?.previousElementSibling?.textContent?.trim()?.toLowerCase() ||
    codeEl.closest("[class*='overflow']")?.previousElementSibling?.textContent?.trim()?.toLowerCase() || "";

  if (prevSibling.includes("python"))     return "script.py";
  if (prevSibling.includes("javascript")) return "script.js";
  if (prevSibling.includes("typescript")) return "script.ts";
  if (prevSibling.includes("json"))       return "package.json";

  const code = (codeEl.innerText || codeEl.textContent) || "";
  if (/^\s*(import |from .+ import|def |class )/.test(code)) return "script.py";
  if (/require\(|import .+ from/.test(code))                  return "script.js";
  if (/"dependencies"\s*:/.test(code))                        return "package.json";
  return "script.py";
}

// ── 패널 삽입 ─────────────────────────────────────────────────────────────────
// div[dir='ltr'] 기준 4단계 위의 border-token-border 컨테이너 다음에 삽입
function insertAfterCodeBlock(codeEl, newEl) {
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
  console.warn("[Slop Detector] ChatGPT 패널 삽입 위치 없음");
  return false;
}

// ── 중복 방지 ─────────────────────────────────────────────────────────────────
let processedKeys = new Set();

function getKey(text) {
  return `${text.length}::${text.slice(0, 60)}::${text.slice(-60)}`;
}

// ── 코드블록 스캔 ─────────────────────────────────────────────────────────────
function scanCodeBlocks() {
  const selectors = ["div[dir='ltr']", "pre code"].join(", ");
  document.querySelectorAll(selectors).forEach(el => {
    // innerText로 줄바꿈 보존
    const text = ((el.innerText || el.textContent) || "").trim();
    if (text.length < 80) return;
    const hasImport = /^\s*(import |from .+ import)/m.test(text)
      || /require\(|"dependencies"/.test(text);
    if (!hasImport) return;
    const key = getKey(text);
    if (processedKeys.has(key)) return;
    processedKeys.add(key);

    const filename = guessFilename(el);
    analyzeAndRender(text, filename, (newEl) => insertAfterCodeBlock(el, newEl));
  });
}

// ── MutationObserver ──────────────────────────────────────────────────────────
const observer = new MutationObserver(() => {
  clearTimeout(observer._timer);
  observer._timer = setTimeout(scanCodeBlocks, 1500);
});

// ── 시작 ──────────────────────────────────────────────────────────────────────
(async () => {
  const serverUp = await checkApiServer();
  console.log(`[Slop Detector] 시작 — 사이트: chatgpt, API: ${serverUp ? "✅ 연결됨" : "❌ 오프라인"}`);
  if (!serverUp) return;

  watchNavigation(() => {
    processedKeys = new Set();
    setTimeout(scanCodeBlocks, 1000);
  });

  scanCodeBlocks();
  observer.observe(document.body, { childList: true, subtree: true });
})();
