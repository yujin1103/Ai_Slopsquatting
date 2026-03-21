from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import httpx
from rapidfuzz import fuzz, distance

app = FastAPI(title="슬롭스쿼팅 분석 API", version="1.0.0")

# 비교 기준 인기 패키지 목록
POPULAR_PACKAGES = [
    "numpy", "pandas", "requests", "flask", "django", "fastapi", "sqlalchemy",
    "pydantic", "pytest", "scipy", "matplotlib", "tensorflow", "torch",
    "scikit-learn", "transformers", "boto3", "celery", "redis", "pillow",
    "aiohttp", "httpx", "uvicorn", "alembic", "psycopg2", "pymongo",
    "jinja2", "click", "typer", "rich", "pyyaml", "python-dotenv",
    "langchain", "openai", "anthropic", "cohere", "huggingface-hub",
    "datasets", "tokenizers", "accelerate", "sentence-transformers",
    "cryptography", "paramiko", "scapy", "beautifulsoup4", "selenium",
    "react", "express", "lodash", "axios", "webpack", "eslint",
    "typescript", "jest", "next", "vue", "angular",
]


class AnalyzeRequest(BaseModel):
    packages: List[str]


class PackageResult(BaseModel):
    package: str
    pypi_exists: bool
    npm_exists: bool
    score: int
    level: str
    signals: List[str]
    closest: str
    min_dist: int
    reg_days: int | None
    version_count: int


@app.get("/health")
def health():
    return {"status": "ok", "service": "slop-detector-api"}


@app.post("/analyze", response_model=List[PackageResult])
async def analyze(req: AnalyzeRequest):
    results = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for pkg in req.packages[:10]:  # 최대 10개
            score = 0
            signals = []
            pypi_exists = False
            npm_exists = False
            reg_days = None
            version_count = 0

            # ── PyPI 조회 ──────────────────────────────────────
            try:
                res = await client.get(
                    f"https://pypi.org/pypi/{pkg}/json",
                    headers={"User-Agent": "slop-detector/1.0"}
                )
                if res.status_code == 200:
                    pypi_exists = True
                    meta = res.json()
                    releases = meta.get("releases", {})
                    version_count = len(releases)

                    all_files = [f for v in releases.values() for f in v]
                    if all_files:
                        from datetime import datetime, timezone
                        dates = [
                            datetime.fromisoformat(
                                f["upload_time"].replace("Z", "+00:00")
                            )
                            for f in all_files if "upload_time" in f
                        ]
                        if dates:
                            oldest = min(dates)
                            now = datetime.now(timezone.utc)
                            reg_days = (now - oldest).days

                            if reg_days < 7:
                                score += 25
                                signals.append(f"⚠️ 7일 이내 신규 등록 ({reg_days}일 전)")
                            elif reg_days < 30:
                                score += 15
                                signals.append(f"⚠️ 30일 이내 등록 ({reg_days}일 전)")
                            else:
                                signals.append(f"✅ 등록 {reg_days}일 경과 (안정적)")

                    if version_count == 1:
                        score += 10
                        signals.append("⚠️ 배포 버전 1개뿐")
                    elif version_count > 1:
                        signals.append(f"✅ 버전 {version_count}개 (활성 패키지)")

                else:
                    score += 55
                    signals.append("🚨 PyPI 미등록 — 존재하지 않는 패키지")

            except Exception as e:
                signals.append(f"❓ PyPI 조회 오류: {str(e)[:50]}")

            # ── npm 크로스 에코시스템 탐지 ──────────────────────
            if not pypi_exists:
                try:
                    npm_res = await client.get(
                        f"https://registry.npmjs.org/{pkg}",
                        headers={"User-Agent": "slop-detector/1.0"}
                    )
                    if npm_res.status_code == 200:
                        npm_exists = True
                        score += 15
                        signals.append("⚠️ npm에는 존재 → 생태계 혼동 패턴")
                    else:
                        signals.append("🚨 npm에도 미등록")
                except Exception:
                    pass

            # ── 혼성형 탐지 ────────────────────────────────────
            parts = [
                p for p in pkg.replace("-", " ").replace("_", " ").split()
                if len(p) > 2 and any(p in pk or pk.startswith(p) for pk in POPULAR_PACKAGES)
            ]
            if len(parts) >= 2:
                score += 20
                signals.append(f"⚠️ 합성 패턴 의심: [{' + '.join(parts)}]")

            # ── 편집 거리 (rapidfuzz) ──────────────────────────
            best_score = 0
            closest = ""
            for known in POPULAR_PACKAGES:
                ratio = fuzz.ratio(pkg, known)
                if ratio > best_score:
                    best_score = ratio
                    closest = known

            min_dist = distance.Levenshtein.distance(pkg, closest)

            if 0 < min_dist <= 2:
                score += 20
                signals.append(f"⚠️ '{closest}'과 매우 유사 (편집거리 {min_dist})")
            elif min_dist <= 4:
                score += 8
                signals.append(f"ℹ️ '{closest}'과 유사 (편집거리 {min_dist})")

            # ── 위험 레벨 결정 ─────────────────────────────────
            final_score = min(score, 100)
            if final_score >= 80:
                level = "CRITICAL"
            elif final_score >= 60:
                level = "HIGH"
            elif final_score >= 30:
                level = "MEDIUM"
            else:
                level = "LOW"

            results.append(PackageResult(
                package=pkg,
                pypi_exists=pypi_exists,
                npm_exists=npm_exists,
                score=final_score,
                level=level,
                signals=signals,
                closest=closest,
                min_dist=min_dist,
                reg_days=reg_days,
                version_count=version_count,
            ))

    return results
