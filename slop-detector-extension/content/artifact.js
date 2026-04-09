/**
 * artifact.js — a.claude.ai iframe 전용
 *
 * 코드 추출 → 분석 → 결과를 부모(claude.ai)로 postMessage
 * 패널 표시는 claude.js가 아티팩트 카드 아래에 담당
 */

function guessFilenameFromCode(code) {
  if (/^\s*(import |from .+ import|def |class )/m.test(code)) return "script.py";
  if (/require\(|import .+ from/.test(code))                   return "script.js";
  if (/"dependencies"\s*:/.test(code))                         return "package.json";
  return "script.py";
}

function extractCode() {
  // Claude 아티팩트 뷰어: token 요소의 3단계 위 div가 코드 전체를 담음
  // div.min-w-0.max-w-full → innerText로 줄바꿈 보존
  const tokenEl = document.querySelector("[class*='token']");
  if (tokenEl) {
    let el = tokenEl;
    for (let i = 0; i < 6; i++) {
      el = el.parentElement;
      if (!el) break;
      const cls = el.className || "";
      if (cls.includes("min-w-0") && cls.includes("max-w-full")) {
        // 줄 번호 제거: 각 줄이 "숫자\n코드" 형태로 되어 있음
        const raw = el.innerText || "";
        const lines = raw.split("\n");
        const code = lines
          .filter((_, i) => i % 2 === 1)  // 홀수 인덱스 = 실제 코드 줄
          .join("\n");
        if (code.length > 30) return code;
      }
    }
  }

  // 폴백: 기존 셀렉터
  const selectors = [".view-lines", ".CodeMirror-code", "pre code", "pre"];
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el) {
      const text = (el.innerText || el.textContent || "").trim();
      if (text.length > 30) return text;
    }
  }
  return null;
}

let analyzed = false;

async function runAnalysis() {
  if (analyzed) return;

  const code = extractCode();
  if (!code) return;

  const hasImport = /^\s*(import |from .+ import)/m.test(code)
    || /require\(|"dependencies"/.test(code);
  if (!hasImport) return;

  const filename = guessFilenameFromCode(code);
  analyzed = true;

  console.log(`[Slop Detector] 아티팩트 분석: ${filename} (${code.length}자)`);

  try {
    const result = await callBackground({ type: "PARSE_AND_ANALYZE", filename, code });
    if (!result?.results?.length) return;

    console.log(`[Slop Detector] 아티팩트 완료:`, result.results.map(r => `${r.package}(${r.level})`));

    // 결과를 부모 페이지로 전송
    window.parent.postMessage({
      type: "SLOP_ARTIFACT_RESULT",
      results: result.results,
    }, "https://claude.ai");

  } catch (err) {
    console.error("[Slop Detector] 아티팩트 오류:", err.message);
  }
}

const observer = new MutationObserver(() => {
  clearTimeout(observer._timer);
  observer._timer = setTimeout(runAnalysis, 1000);
});

(async () => {
  const serverUp = await checkApiServer();
  console.log(`[Slop Detector] 아티팩트 iframe, API: ${serverUp ? "✅" : "❌"}`);
  if (!serverUp) return;

  setTimeout(runAnalysis, 800);
  observer.observe(document.body, { childList: true, subtree: true });
})();
