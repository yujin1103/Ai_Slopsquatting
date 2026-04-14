/**
 * background.js — Service Worker
 */

const API_BASE = "http://localhost:8001";

// ── 성능 향상: 중복 요청 방지를 위한 메모리 캐시 ──────────────────────────────
const analysisCache = new Map();
const CACHE_TTL = 1000 * 60 * 30; // 30분 유지

function getFromCache(key) {
  const cached = analysisCache.get(key);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }
  return null;
}

function setCache(key, data) {
  analysisCache.set(key, { data, timestamp: Date.now() });
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256",
    new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, "0")).join("");
}

// ── 위험도 상태 관리 ────────────────────────────────────────────────────────
async function updateRiskState(analysisResult) {
  // 결과에서 슬롭스쿼팅 등 고위험 패키지가 있는지 확인 후 스토리지에 저장
  // 예: result 내에 riskLevel 속성이 있다고 가정
  chrome.storage.local.get(['scanStats'], (res) => {
    const stats = res.scanStats || { safe: 0, suspicious: 0, malicious: 0 };
    
    if (analysisResult.riskLevel === 'malicious') stats.malicious++;
    else if (analysisResult.riskLevel === 'suspicious') stats.suspicious++;
    else stats.safe++;

    chrome.storage.local.set({ scanStats: stats });
  });
}

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
  const cacheKey = `pkg_${await sha256(packages.sort().join(","))}`;
  const cached = getFromCache(cacheKey);
  if (cached) return cached;

  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ packages }),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`API 오류: ${res.status}`);
  
  const data = await res.json();
  setCache(cacheKey, data);
  await updateRiskState(data);
  return data;
}

// ── 코드 파싱 + 분석 ─────────────────────────────────────────────────────────
async function parseAndAnalyze(filename, code) {
  const cacheKey = `code_${await sha256(filename + code)}`;
  const cached = getFromCache(cacheKey);
  if (cached) return cached;

  const res = await fetch(`${API_BASE}/parse-and-analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, code }),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`API 오류: ${res.status}`);
  
  const data = await res.json();
  setCache(cacheKey, data);
  await updateRiskState(data);
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
        const codeIn = (message.code || "").replace(/\u00a0/g, " ");
        return await parseAndAnalyze(message.filename, codeIn);
      }
      case "GET_STATS":
        return new Promise((resolve) => {
          chrome.storage.local.get(['scanStats'], (res) => resolve(res.scanStats || null));
        });
      default:
        return { error: `알 수 없는 메시지 타입: ${message.type}` };
    }
  };

  handle()
    .then(sendResponse)
    .catch((err) => sendResponse({ error: err.message }));

  return true;
});