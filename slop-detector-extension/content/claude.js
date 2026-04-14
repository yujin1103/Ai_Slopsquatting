/**
 * claude.js — claude.ai 전용
 *
 * 케이스 1: 코드블록 (pre code) → scanCodeBlocks()
 * 케이스 2: 아티팩트 뷰어 코드 → scanArtifacts()
 *           top DOM의 [class*='token'] → min-w-0.max-w-full 컨테이너에서 추출
 *           아티팩트 카드 부모(rounded-lg) 다음에 패널 삽입
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
  if (/^\s*(import |from .+ import|def |class )/m.test(code)) return "script.py";
  if (/require\(|import .+ from/.test(code))                   return "script.js";
  if (/"dependencies"\s*:/.test(code))                         return "package.json";
  return "script.py";
}

function guessFilenameFromCode(code) {
  if (/^\s*(import |from .+ import|def |class )/m.test(code)) return "script.py";
  if (/require\(|import .+ from/.test(code))                   return "script.js";
  if (/"dependencies"\s*:/.test(code))                         return "package.json";
  return "script.py";
}

// ── DOM 삽입 ─────────────────────────────────────────────────────────────────
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
const processedArtifacts = new Set();

function getKey(text) {
  return `${text.length}::${text.slice(0, 60)}::${text.slice(-60)}`;
}

// ── 케이스 1: 코드블록 스캔 ──────────────────────────────────────────────────
function scanCodeBlocks() {
  document.querySelectorAll("pre code").forEach(el => {
    const text = (el.textContent || "").trim();
    if (text.length < 80) return;
    const hasImport = /^\s*(import |from .+ import)/m.test(text)
      || /require\(|"dependencies"/.test(text);
    if (!hasImport) return;
    const key = getKey(text);
    if (processedKeys.has(key)) return;
    processedKeys.add(key);
    const filename = guessFilename(el);
    analyzeAndRender(text, filename, (newEl) => insertAfterCode(el, newEl));
  });
}

// ── 케이스 2: 아티팩트 코드 추출 ─────────────────────────────────────────────
function extractArtifactCode() {
  const tokenEl = document.querySelector("[class*='token']");
  if (!tokenEl) return null;

  let el = tokenEl;
  for (let i = 0; i < 8; i++) {
    el = el.parentElement;
    if (!el) break;
    const cls = el.className || "";
    if (cls.includes("min-w-0") && cls.includes("max-w-full")) {
      const raw = el.innerText || "";
      const lines = raw.split("\n");
      // 줄번호 있는 구조: "1\nimport numpy\n2\nimport pandas" → 홀수 인덱스가 코드
      const isNumbered = /^\d+$/.test(lines[0]?.trim());
      return isNumbered
        ? lines.filter((_, i) => i % 2 === 1).join("\n")
        : raw;
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

  const key = `artifact::${getKey(code)}`;
  if (processedArtifacts.has(key)) return;
  processedArtifacts.add(key);

  const filename = guessFilenameFromCode(code);
  console.log(`[Slop Detector] 아티팩트 감지: ${filename} (${code.length}자)`);

  // 아직 분석 안 된 첫 번째 카드를 미리 예약 (로딩/패널 모두 같은 카드에)
  const cards = [...document.querySelectorAll("[class*='artifact-block']")];
  const targetCard = cards.find(c => !c.hasAttribute("data-slop-analyzed"));
  if (!targetCard) return; // 모든 카드가 이미 분석됨

  targetCard.setAttribute("data-slop-analyzed", "1"); // 예약 마킹

  const insertFn = (newEl) => {
    newEl.setAttribute("data-slop-artifact-panel", "1");
    newEl.style.margin = "4px 0 0";
    const rowContainer = targetCard
      ?.parentElement?.parentElement?.parentElement?.parentElement;
    if (rowContainer) {
      // 기존 패널 제거 후 삽입
      let next = rowContainer.nextElementSibling;
      while (next?.hasAttribute("data-slop-artifact-panel")) {
        const toRemove = next;
        next = next.nextElementSibling;
        toRemove.remove();
      }
      try {
        rowContainer.insertAdjacentElement("afterend", newEl);
        return true;
      } catch {}
    }
    return false;
  };

  analyzeAndRender(code, filename, insertFn);
}

// ── MutationObserver ──────────────────────────────────────────────────────────
const observer = new MutationObserver(() => {
  clearTimeout(observer._timer);
  observer._timer = setTimeout(() => {
    scanCodeBlocks();
    scanArtifacts();
    scanResponseText();
  }, 1500);
});

// ── 아티팩트 결과 수신 (postMessage from a.claude.ai iframe) ─────────────────
window.addEventListener("message", (event) => {
  if (event.origin !== "https://a.claude.ai") return;
  if (event.data?.type !== "SLOP_ARTIFACT_RESULT") return;
  const results = event.data.results;
  if (!results?.length) return;
  console.log(`[Slop Detector] postMessage 수신:`, results.map(r => `${r.package}(${r.level})`));
});

// ── 시작 ──────────────────────────────────────────────────────────────────────
(async () => {
  const serverUp = await checkApiServer();
  console.log(`[Slop Detector] 시작 — 사이트: claude, API: ${serverUp ? "✅ 연결됨" : "❌ 오프라인"}`);
  if (!serverUp) return;

  watchNavigation(() => {
    processedKeys = new Set();
    processedArtifacts.clear();
    // 아티팩트 카드 분석 마킹 초기화
    document.querySelectorAll("[data-slop-analyzed]").forEach(el => el.removeAttribute("data-slop-analyzed"));
    setTimeout(() => { scanCodeBlocks(); scanArtifacts(); }, 1000);
  });

  scanCodeBlocks();
  scanArtifacts();
  scanResponseText();
  observer.observe(document.body, { childList: true, subtree: true });
})();

// ── 텍스트 응답 스캔 (pip/npm install 패턴 + table td strong) ────────────────
const processedTextKeys = new Set();

// Claude 표시명 → PyPI/npm 패키지명 매핑
const CLAUDE_PACKAGE_MAP = {
  "scikit-learn": "scikit-learn",
  "sklearn": "scikit-learn",
  "tensorflow": "tensorflow",
  "pytorch": "torch",
  "keras": "keras",
  "xgboost": "xgboost",
  "lightgbm": "lightgbm",
  "hugging face": "transformers",
  "transformers": "transformers",
  "numpy": "numpy",
  "pandas": "pandas",
  "matplotlib": "matplotlib",
  "opencv": "opencv-python",
  "fastapi": "fastapi",
  "flask": "flask",
  "django": "django",
  "requests": "requests",
  "scipy": "scipy",
};

function extractTablePackages(el) {
  // Claude 표(table) 안의 td > strong 태그에서 패키지명 추출
  const packages = new Set();
  el.querySelectorAll("table td strong").forEach(strong => {
    const name = strong.textContent.trim().toLowerCase();
    if (CLAUDE_PACKAGE_MAP[name]) {
      packages.add(CLAUDE_PACKAGE_MAP[name]);
    } else if (/^[a-z0-9][a-z0-9\-\.]+$/.test(name) && name.length < 40) {
      packages.add(name);
    }
  });
  return [...packages];
}

function scanResponseText() {
  // Claude 응답 컨테이너
  document.querySelectorAll(
    ".prose, [class*='prose'], div[data-is-streaming='false'], .font-claude-message"
  ).forEach(el => {
    const text = el.innerText || "";
    if (text.length < 20) return;

    const key = `text::${text.length}::${text.slice(0, 60)}`;
    if (processedTextKeys.has(key)) return;

    // 1. pip/npm install 패턴
    const pipPackages = extractPackagesFromText(text);

    // 2. table td > strong 태그 (Claude 패키지 소개 표)
    const tablePackages = extractTablePackages(el);

    const allPackages = [...new Set([...pipPackages, ...tablePackages])]
      .filter(p => ![...processedKeys].some(k => k.includes(p)));

    if (!allPackages.length) return;

    // DOM에 이미 텍스트 패널이 있으면 스킵
    if (el.parentElement?.querySelector("[data-slop-text-panel]")) return;

    processedTextKeys.add(key);
    console.log(`[Slop Detector] Claude 텍스트 패키지 감지:`, allPackages);

    analyzePackagesFromText(allPackages, (newEl) => {
      newEl.setAttribute("data-slop-text-panel", "1");
      const existingPanel = el.nextElementSibling?.hasAttribute("data-slop-panel")
        ? el.nextElementSibling : null;
      const insertTarget = existingPanel || el;
      try { insertTarget.insertAdjacentElement("afterend", newEl); return true; } catch {}
      return false;
    });
  });
}
