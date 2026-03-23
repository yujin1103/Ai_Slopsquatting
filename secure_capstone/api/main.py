"""
main.py  —  슬롭스쿼팅 분석 API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
엔드포인트:
  GET  /health               서버 상태 확인
  POST /analyze              패키지명 목록 → 각 패키지 위험도 분석
  POST /parse                소스코드 → import 추출 (AST + Regex 하이브리드)
  POST /parse-and-analyze    소스코드 → 추출 + 위험도 분석 한 번에
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from rapidfuzz import distance, fuzz

from import_parser import parse_code  # 하이브리드 파서

app = FastAPI(title="슬롭스쿼팅 분석 API", version="2.0.0")


# ── 인기 패키지 목록 로드 ──────────────────────────────────────────────────────
def _load_popular_packages() -> list[str]:
    data_file = Path(__file__).parent / "data" / "popular_python_packages.txt"
    if not data_file.exists():
        return []
    return [
        line.strip()
        for line in data_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


POPULAR_PACKAGES: list[str] = _load_popular_packages()
POPULAR_PACKAGES_SET: set[str] = set(POPULAR_PACKAGES)  # O(1) 조회용


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic 모델
# ══════════════════════════════════════════════════════════════════════════════

class AnalyzeRequest(BaseModel):
    packages: List[str]


class ParseRequest(BaseModel):
    filename: str   # 확장자로 언어 감지 (예: "script.py", "index.ts")
    code: str


class PackageResult(BaseModel):
    package: str
    pypi_exists: bool
    npm_exists: bool
    ecosystem: str          # "python" | "npm" | "both" | "unknown"
    is_dynamic: bool        # True → importlib 등 동적 import 경유
    score: int
    level: str              # LOW | MEDIUM | HIGH | CRITICAL
    signals: List[str]
    closest: str
    min_dist: int
    reg_days: int | None
    version_count: int


class ParseResponse(BaseModel):
    filename: str
    language: str
    parse_method: str
    static_packages: List[str]
    dynamic_packages: List[str]
    total: int


class ParseAndAnalyzeResponse(BaseModel):
    filename: str
    language: str
    parse_method: str
    static_count: int
    dynamic_count: int
    results: List[PackageResult]


# ══════════════════════════════════════════════════════════════════════════════
# 핵심 분석 로직 (엔드포인트에서 공유)
# ══════════════════════════════════════════════════════════════════════════════

async def _analyse_package(
    pkg: str,
    client: httpx.AsyncClient,
    is_dynamic: bool = False,
) -> PackageResult:
    """패키지 하나를 PyPI·npm·유사도 기준으로 분석하고 PackageResult 반환."""

    score = 0
    signals: list[str] = []
    pypi_exists = False
    npm_exists = False
    reg_days: int | None = None
    version_count = 0

    # 동적 import 플래그 시그널
    if is_dynamic:
        signals.append("🔍 동적 import 탐지 (importlib / __import__ 등) — 주의 필요")

    # ── PyPI 조회 ──────────────────────────────────────────────────────────────
    try:
        res = await client.get(
            f"https://pypi.org/pypi/{pkg}/json",
            headers={"User-Agent": "slop-detector/2.0"},
        )
        if res.status_code == 200:
            pypi_exists = True
            meta = res.json()
            releases = meta.get("releases", {})
            version_count = len(releases)

            all_files = [f for v in releases.values() for f in v]
            if all_files:
                dates = [
                    datetime.fromisoformat(f["upload_time"].replace("Z", "+00:00"))
                    for f in all_files
                    if "upload_time" in f
                ]
                if dates:
                    oldest = min(dates)
                    reg_days = (datetime.now(timezone.utc) - oldest).days

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

    # ── npm 크로스 에코시스템 탐지 ────────────────────────────────────────────
    if not pypi_exists:
        try:
            npm_res = await client.get(
                f"https://registry.npmjs.org/{pkg}",
                headers={"User-Agent": "slop-detector/2.0"},
            )
            if npm_res.status_code == 200:
                npm_exists = True
                score += 15
                signals.append("⚠️ npm에는 존재 → 생태계 혼동 패턴")
            else:
                signals.append("🚨 npm에도 미등록")
        except Exception:
            pass

    # ── 에코시스템 결정 ────────────────────────────────────────────────────────
    if pypi_exists and npm_exists:
        ecosystem = "both"
    elif pypi_exists:
        ecosystem = "python"
    elif npm_exists:
        ecosystem = "npm"
    else:
        ecosystem = "unknown"

    # ── 합성 패턴 탐지 (정확 매칭) ────────────────────────────────────────────
    # 패키지명을 분리했을 때 각 파트가 독립적인 유명 패키지와 정확히 일치할 때만 의심
    # 예) flask_redis → ["flask", "redis"] 둘 다 인기 패키지 → 의심
    # 예) python-dotenv → ["python", "dotenv"] 둘 다 해당 없음 → 오탐 방지
    parts = [
        p for p in pkg.replace("-", " ").replace("_", " ").split()
        if len(p) > 2 and p in POPULAR_PACKAGES_SET
    ]
    if len(parts) >= 2:
        score += 20
        signals.append(f"⚠️ 합성 패턴 의심: [{' + '.join(parts)}]")

    # ── 편집 거리 유사도 (rapidfuzz) ──────────────────────────────────────────
    best_ratio = 0
    closest = ""
    for known in POPULAR_PACKAGES:
        ratio = fuzz.ratio(pkg, known)
        if ratio > best_ratio:
            best_ratio = ratio
            closest = known

    min_dist = distance.Levenshtein.distance(pkg, closest)

    if 0 < min_dist <= 2:
        score += 20
        signals.append(f"⚠️ '{closest}'과 매우 유사 (편집거리 {min_dist})")
    elif min_dist <= 4:
        score += 8
        signals.append(f"ℹ️ '{closest}'과 유사 (편집거리 {min_dist})")

    # ── 위험 레벨 결정 ─────────────────────────────────────────────────────────
    final_score = min(score, 100)
    if final_score >= 80:
        level = "CRITICAL"
    elif final_score >= 60:
        level = "HIGH"
    elif final_score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    return PackageResult(
        package=pkg,
        pypi_exists=pypi_exists,
        npm_exists=npm_exists,
        ecosystem=ecosystem,
        is_dynamic=is_dynamic,
        score=final_score,
        level=level,
        signals=signals,
        closest=closest,
        min_dist=min_dist,
        reg_days=reg_days,
        version_count=version_count,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 엔드포인트
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "slop-detector-api",
        "version": "2.0.0",
        "popular_packages_loaded": len(POPULAR_PACKAGES),
    }


@app.post("/analyze", response_model=List[PackageResult])
async def analyze(req: AnalyzeRequest):
    """패키지명 목록을 받아 각 패키지의 위험도를 분석한다."""
    results: list[PackageResult] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for pkg in req.packages[:10]:  # 최대 10개
            result = await _analyse_package(pkg, client)
            results.append(result)
    return results


@app.post("/parse", response_model=ParseResponse)
def parse(req: ParseRequest):
    """
    소스코드에서 import 패키지명을 추출한다.

    - .py  → AST(정적) + 정규식(동적) 하이브리드
    - .js/.ts 등 → 정규식
    - package.json → JSON 파싱
    """
    result = parse_code(req.filename, req.code)
    return ParseResponse(
        filename=req.filename,
        language=result.language,
        parse_method=result.parse_method,
        static_packages=result.packages,
        dynamic_packages=result.dynamic_packages,
        total=len(result.packages) + len(result.dynamic_packages),
    )


@app.post("/parse-and-analyze", response_model=ParseAndAnalyzeResponse)
async def parse_and_analyze(req: ParseRequest):
    """
    소스코드에서 import 추출 → 위험도 분석까지 한 번에 수행.

    동적 import(importlib 등)는 is_dynamic=True 플래그와 별도 시그널로 표시된다.
    """
    # Step 1: 하이브리드 파싱
    parse_result = parse_code(req.filename, req.code)

    # Step 2: 모든 패키지 분석 (정적 + 동적 합산, 최대 20개)
    static_set = set(parse_result.packages)
    all_packages = parse_result.packages + parse_result.dynamic_packages
    all_packages = list(dict.fromkeys(all_packages))[:20]  # 중복 제거, 순서 유지

    results: list[PackageResult] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for pkg in all_packages:
            is_dynamic = pkg not in static_set
            result = await _analyse_package(pkg, client, is_dynamic=is_dynamic)
            results.append(result)

    return ParseAndAnalyzeResponse(
        filename=req.filename,
        language=parse_result.language,
        parse_method=parse_result.parse_method,
        static_count=len(parse_result.packages),
        dynamic_count=len(parse_result.dynamic_packages),
        results=results,
    )
