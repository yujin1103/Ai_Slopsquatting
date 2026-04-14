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

function getKey(text) {
  return `${text.length}::${text.slice(0, 60)}::${text.slice(-60)}`;
}

// 아티팩트 분석 상태: 스트리밍 중 debounce + 카드 잠금
let _artifactTimer = null;
let _pendingCard = null;

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
  // 토큰 요소가 있는 모든 코드 컨테이너를 찾음
  const tokenEls = document.querySelectorAll("[class*='token']");
  if (!tokenEls.length) return null;

  // 토큰에서 상위 코드 컨테이너를 찾는 함수
  function findCodeContainer(tokenEl) {
    let el = tokenEl;
    let bestContainer = null;
    for (let i = 0; i < 12; i++) {
      el = el.parentElement;
      if (!el || el === document.body) break;

      const tokenCount = el.querySelectorAll("[class*='token']").length;
      const text = el.innerText || "";

      // 토큰이 5개 이상이고 텍스트가 충분한 컨테이너
      if (tokenCount >= 5 && text.length > 80) {
        bestContainer = el;
        // 더 위로 올라가면 전체 페이지를 잡을 수 있으므로
        // 토큰 밀도가 급격히 떨어지면 멈춤
        const parentTokens = el.parentElement?.querySelectorAll("[class*='token']").length || 0;
        if (parentTokens > tokenCount * 3) break;
      }
    }
    return bestContainer;
  }

  // 첫 번째 토큰에서 코드 컨테이너 탐색
  const container = findCodeContainer(tokenEls[0]);
  if (!container) return null;

  const raw = container.innerText || "";
  if (raw.length < 80) return null;

  // 줄번호 제거: "1\nimport flask\n2\nfrom flask..." 형태
  const lines = raw.split("\n");
  const isNumbered = /^\d+$/.test(lines[0]?.trim());
  const code = isNumbered
    ? lines.filter((_, i) => i % 2 === 1).join("\n")
    : raw;

  return code.length > 30 ? code : null;
}

function scanArtifacts() {
  const code = extractArtifactCode();
  if (!code || code.length < 80) return;

  const hasImport = /^\s*(import |from .+ import)/m.test(code)
    || /require\(|"dependencies"/.test(code);
  if (!hasImport) return;

  // ── 스트리밍 중 debounce ────────────────────────────────────────
  // 이미 타이머가 돌고 있으면 (같은 아티팩트의 스트리밍 중) 타이머만 리셋
  if (_artifactTimer) {
    clearTimeout(_artifactTimer);
    _artifactTimer = setTimeout(() => _analyzeStableArtifact(), 2000);
    return;
  }

  // ── 새 아티팩트 감지: 카드를 즉시 잠금 ─────────────────────────
  const cards = [...document.querySelectorAll("[class*='artifact-block']")];
  const targetCard = cards.find(c => !c.hasAttribute("data-slop-analyzed"));
  if (!targetCard) return;

  targetCard.setAttribute("data-slop-analyzed", "1");
  _pendingCard = targetCard;

  // 스트리밍이 안정될 때까지 대기 (2초간 변화 없으면 분석 실행)
  _artifactTimer = setTimeout(() => _analyzeStableArtifact(), 2000);
}

function _analyzeStableArtifact() {
  _artifactTimer = null;
  const card = _pendingCard;
  _pendingCard = null;
  if (!card) return;

  // 안정화된 최종 코드 다시 추출
  const code = extractArtifactCode();
  if (!code || code.length < 80) {
    card.removeAttribute("data-slop-analyzed");
    return;
  }

  const filename = guessFilenameFromCode(code);
  console.log(`[Slop Detector] 아티팩트 분석 시작: ${filename} (${code.length}자)`);

  analyzeAndRender(code, filename, (newEl) => {
    newEl.setAttribute("data-slop-artifact-panel", "1");
    newEl.style.margin = "4px 0 0";
    const rowContainer = card
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
  });
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
const _processedArtifactMessages = new Set();

window.addEventListener("message", (event) => {
  const allowed = ["https://a.claude.ai", "https://www.claudeusercontent.com"];
  if (!allowed.some(o => event.origin === o || event.origin.endsWith(".claudeusercontent.com"))) return;
  if (event.data?.type !== "SLOP_ARTIFACT_RESULT") return;
  const results = event.data.results;
  if (!results?.length) return;

  // 중복 방지: 패키지 조합 기반
  const msgKey = results.map(r => r.package).sort().join(",");
  if (_processedArtifactMessages.has(msgKey)) return;
  _processedArtifactMessages.add(msgKey);

  console.log(`[Slop Detector] 아티팩트 iframe 결과 수신:`, results.map(r => `${r.package}(${r.level})`));

  const panel = buildPanel(results);
  panel.setAttribute("data-slop-artifact-panel", "1");
  panel.style.margin = "4px 0 0";

  // 전략 1: artifact-block 카드 찾기
  const cards = [...document.querySelectorAll("[class*='artifact-block']")];
  const targetCard = cards.find(c => !c.hasAttribute("data-slop-analyzed"));

  if (targetCard) {
    targetCard.setAttribute("data-slop-analyzed", "1");
    const rowContainer = targetCard
      ?.parentElement?.parentElement?.parentElement?.parentElement;
    if (rowContainer) {
      let next = rowContainer.nextElementSibling;
      while (next?.hasAttribute("data-slop-artifact-panel")) {
        const toRemove = next;
        next = next.nextElementSibling;
        toRemove.remove();
      }
      try { rowContainer.insertAdjacentElement("afterend", panel); return; } catch {}
    }
  }

  // 전략 2: 대화 내 마지막 응답 블록 뒤에 삽입
  const responseBlocks = document.querySelectorAll(
    ".font-claude-message, [class*='prose'], div[data-is-streaming='false']"
  );
  const lastBlock = responseBlocks[responseBlocks.length - 1];
  if (lastBlock) {
    // 기존 아티팩트 패널이 있으면 제거
    const existing = lastBlock.parentElement?.querySelector("[data-slop-artifact-panel]");
    if (existing) existing.remove();
    try { lastBlock.insertAdjacentElement("afterend", panel); return; } catch {}
  }

  // 전략 3: 대화 컨테이너 끝에 추가
  const chatContainer = document.querySelector("[class*='conversation'], main, [role='main']");
  if (chatContainer) {
    try { chatContainer.appendChild(panel); } catch {}
  }
});

// ── 시작 ──────────────────────────────────────────────────────────────────────
(async () => {
  const serverUp = await checkApiServer();
  console.log(`[Slop Detector] 시작 — 사이트: claude, API: ${serverUp ? "✅ 연결됨" : "❌ 오프라인"}`);
  if (!serverUp) return;

  watchNavigation(() => {
    processedKeys = new Set();
    clearTimeout(_artifactTimer);
    _artifactTimer = null;
    _pendingCard = null;
    _processedArtifactMessages.clear();
    // 아티팩트 카드 분석 마킹 초기화
    document.querySelectorAll("[data-slop-analyzed]").forEach(el => el.removeAttribute("data-slop-analyzed"));
    document.querySelectorAll("[data-slop-artifact-panel]").forEach(el => el.remove());
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
