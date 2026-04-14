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

// ── 텍스트에서 패키지명 추출 ─────────────────────────────────────────────────
// pip install, npm install 패턴을 텍스트 전체에서 탐지
function extractPackagesFromText(text) {
  const packages = new Set();

  const patterns = [
    // pip install pkg1 pkg2 / pip install pkg==1.0
    /(?:^|[\s`])(?:!|%)?pip(?:3)?\s+install\s+([\w\-\.\[\],\s>=<!]+?)(?=\n|$|`|;)/gm,
    // npm install pkg / npm i pkg
    /(?:^|[\s`])npm\s+(?:install|i)\s+([\w\-@\/\s]+?)(?=\n|$|`|;)/gm,
    // pip install -r 는 제외
  ];

  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      const raw = match[1];
      // 각 패키지명 파싱
      raw.split(/[\s,]+/).forEach(pkg => {
        // 버전 지정자 제거: requests>=2.0 → requests
        pkg = pkg.replace(/[><=!].*/,'').replace(/\[.*\]/,'').trim();
        // 유효성 검사
        if (pkg.length < 2) return;
        if (pkg.startsWith('-')) return;          // -r, --upgrade 등 플래그
        if (pkg.includes('.py')) return;          // 파일명
        if (/^[A-Z][A-Z]/.test(pkg)) return;     // 상수형 대문자
        if (/^\d/.test(pkg)) return;              // 숫자로 시작
        packages.add(pkg);
      });
    }
  }

  return [...packages];
}

// ── 자연어 텍스트에서 패키지명 추출 (백틱 + import + 인기 패키지 매칭) ─────────
// pip install 패턴이 없는 텍스트 응답에서도 패키지명을 감지
const POPULAR_PACKAGES = new Set([
  // Python
  "numpy","pandas","flask","django","fastapi","requests","scipy","matplotlib",
  "tensorflow","pytorch","torch","keras","scikit-learn","sklearn","opencv-python",
  "pillow","beautifulsoup4","bs4","selenium","scrapy","celery","redis","sqlalchemy",
  "alembic","pydantic","httpx","aiohttp","uvicorn","gunicorn","pytest","black",
  "mypy","ruff","poetry","pipenv","transformers","datasets","langchain","openai",
  "anthropic","gradio","streamlit","plotly","seaborn","bokeh","dash","sympy",
  "networkx","nltk","spacy","gensim","xgboost","lightgbm","catboost","optuna",
  "ray","dask","polars","pyarrow","fastparquet","duckdb","pymongo","psycopg2",
  "mysqlclient","peewee","tortoise-orm","motor","mongoengine","marshmallow",
  "pyyaml","toml","dotenv","python-dotenv","click","typer","rich","tqdm",
  "loguru","sentry-sdk","cryptography","bcrypt","jwt","pyjwt","paramiko",
  "fabric","boto3","google-cloud-storage","azure-storage-blob",
  // npm
  "express","react","next","vue","nuxt","angular","svelte","axios","lodash",
  "moment","dayjs","date-fns","cheerio","puppeteer","playwright","jest","mocha",
  "chai","vitest","webpack","vite","rollup","esbuild","tailwindcss","prisma",
  "sequelize","mongoose","typeorm","knex","socket.io","ws","cors","helmet",
  "dotenv","jsonwebtoken","bcryptjs","passport","multer","sharp","nodemailer",
  "bull","ioredis","pg","mysql2","mongodb","zod","yup","joi",
]);

// 오탐 방지: 일반 영어 단어/프로그래밍 키워드
const NLP_STOPWORDS = new Set([
  "the","and","for","with","that","this","from","can","you","use","your",
  "will","not","are","have","more","any","all","it","is","in","or","as",
  "an","to","a","be","has","was","were","been","being","do","does","did",
  "but","if","then","else","when","where","how","what","which","who",
  "pip","npm","install","python","node","import","export","require","module",
  "function","class","def","return","const","let","var","true","false",
  "none","null","self","async","await","try","catch","finally","throw",
  "new","delete","typeof","instanceof","void","yield","super","extends",
  "implements","interface","enum","type","public","private","protected",
  "static","final","abstract","package","default","case","switch","break",
  "continue","while","for","do","if","else","elif","except","raise",
  "pass","lambda","with","as","global","nonlocal","assert","yield",
  "string","number","boolean","object","array","list","dict","set","tuple",
  "int","float","double","long","short","byte","char","bool","str",
  "print","console","log","error","warning","debug","info",
  "http","https","api","url","uri","html","css","json","xml","sql",
  "get","post","put","delete","patch","head","options",
  "app","server","client","database","table","column","row","key","value",
  "file","path","dir","folder","name","index","main","test","config",
  "data","model","view","controller","service","repository","handler",
  "input","output","result","response","request","query","param","body",
  "header","cookie","session","token","auth","user","admin","role",
  "code","script","style","image","video","audio","font","icon",
  "hello","world","example","sample","demo","foo","bar","baz",
]);

function extractPackagesFromNaturalText(text) {
  const found = new Set();

  // 1) 백틱 인라인 코드: `package-name`
  const backtickRe = /`([a-zA-Z][a-zA-Z0-9_\-\.]{1,40})`/g;
  let m;
  while ((m = backtickRe.exec(text)) !== null) {
    const name = m[1].toLowerCase().trim();
    if (_isLikelyPackage(name)) found.add(name);
  }

  // 2) import 패턴 (코드블록 밖 텍스트에서도 감지)
  const importRe = /(?:^|\n)\s*(?:import\s+([\w\-]+)|from\s+([\w\-]+)\s+import)/gm;
  while ((m = importRe.exec(text)) !== null) {
    const name = (m[1] || m[2]).toLowerCase().trim();
    if (_isLikelyPackage(name)) found.add(name);
  }

  // 3) 인기 패키지 사전 매칭 (단어 경계 기반)
  for (const pkg of POPULAR_PACKAGES) {
    // 패키지명이 2글자 이하면 오탐 위험 → 스킵
    if (pkg.length <= 2) continue;
    // 단어 경계로 매칭 (대소문자 무시)
    const re = new RegExp(`(?:^|[\\s\`"'(\\[,;:])${escapeRegex(pkg)}(?:$|[\\s\`"')\\],;:.!?])`, "im");
    if (re.test(text)) found.add(pkg);
  }

  return [...found];
}

function _isLikelyPackage(name) {
  if (name.length < 2 || name.length > 40) return false;
  if (NLP_STOPWORDS.has(name)) return false;
  if (/^\d/.test(name)) return false;
  if (/\.(py|js|ts|html|css|json|md|txt|yaml|yml)$/i.test(name)) return false;
  // PascalCase 클래스명 제외: MyClass, ImageData
  if (/^[A-Z][a-z]+([A-Z][a-z]+)+$/.test(name)) return false;
  return true;
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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

    // Layer 1
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

    // Layer 2
    const L2 = document.createElement("div");
    L2.style.cssText = `margin:0 0 0 12px;padding:4px 7px;background:${hasSrc ? "#fff7ed" : "#f0fdf4"};border-left:2px solid ${hasSrc ? "#f97316" : "#22c55e"};border-radius:0 3px 3px 0;font-size:11px;`;
    if (r.source_analyzed) {
      L2.innerHTML = `
        <b style="color:#475569;">L2 소스 분석</b>
        <span style="color:#94a3b8;"> · 원본 ${r.source_score ?? 0}점${r.score !== r.source_score ? ` + 메타 보조 → ${r.score}점` : ""}</span><br>
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

  try {
    const result = await callBackground({ type: "PARSE_AND_ANALYZE", filename, code });
    loading.remove();
    if (!result?.results?.length) return;
    console.log(`[Slop Detector] 완료:`, result.results.map(r => `${r.package}(${r.level})`));
    insertFn(buildPanel(result.results));
  } catch (err) {
    console.error("[Slop Detector] 오류:", err.message);
    loading.textContent = `⚠️ Slop Detector 오류: ${err.message}`;
    setTimeout(() => loading.remove(), 5000);
  }
}

// ── 텍스트에서 직접 패키지 분석 ──────────────────────────────────────────────
async function analyzePackagesFromText(packages, insertFn) {
  if (!packages.length) return;

  const loading = document.createElement("div");
  loading.setAttribute("data-slop-panel", "1");
  loading.style.cssText = "font-size:11px;color:#94a3b8;padding:3px 2px;font-family:sans-serif;";
  loading.textContent = "🔍 Slop Detector 분석 중...";
  if (!insertFn(loading)) return;

  try {
    const result = await callBackground({ type: "ANALYZE_PACKAGES", packages });
    loading.remove();
    if (!result?.length) return;
    console.log(`[Slop Detector] 텍스트 분석 완료:`, result.map(r => `${r.package}(${r.level})`));
    insertFn(buildPanel(result));
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
