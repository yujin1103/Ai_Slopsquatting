/**
 * background.js — Service Worker
 *
 * content.js는 claude.ai 등 외부 사이트의 CSP 때문에
 * localhost로 직접 fetch를 보낼 수 없습니다.
 * 이 파일이 중계 역할을 합니다.
 *
 * 메시지 흐름:
 *   content.js  →  chrome.runtime.sendMessage()
 *               →  background.js (여기)
 *               →  localhost:8001
 *               →  background.js
 *               →  sendResponse()
 *               →  content.js
 */

const API_BASE = "http://localhost:8001";

// ── 헬스체크 ────────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

// ── 패키지 분석 ─────────────────────────────────────────────────────────────
async function analyzePackages(packages) {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ packages }),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`API 오류: ${res.status}`);
  return res.json();
}

// ── 코드 파싱 + 분석 ─────────────────────────────────────────────────────────
async function parseAndAnalyze(filename, code) {
  const res = await fetch(`${API_BASE}/parse-and-analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, code }),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`API 오류: ${res.status}`);
  const data = await res.json();
  return data;
}

// ── 메시지 핸들러 ────────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const handle = async () => {
    switch (message.type) {
      case "HEALTH_CHECK":
        return { ok: await checkHealth() };

      case "ANALYZE_PACKAGES":
        return await analyzePackages(message.packages);

      case "PARSE_AND_ANALYZE": {
        // \xa0 (Non-Breaking Space) → 일반 스페이스로 치환
        // 아티팩트 뷰어 빈 줄에 \xa0가 섞이면 Python AST가 SyntaxError를 냄
        const codeIn = (message.code || "").replace(/\u00a0/g, " ");
        return await parseAndAnalyze(message.filename, codeIn);
      }

      default:
        return { error: `알 수 없는 메시지 타입: ${message.type}` };
    }
  };

  handle()
    .then(sendResponse)
    .catch((err) => sendResponse({ error: err.message }));

  return true; // 비동기 응답을 위해 반드시 true 반환
});
