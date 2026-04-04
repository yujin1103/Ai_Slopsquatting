"""
비동기 PyPI / npm 패키지 검증 모듈 (연구 파이프라인용)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
LLM 할루시네이션 연구 전용 — 패키지 존재 여부 판정에 집중.
소스코드 악성 분석은 api/main.py (실제 탐지 도구)에서 수행.

- 존재 여부 확인 (PyPI / npm)
- 등록일, 버전 수 수집
- 할루시네이션 여부 판정
- 유사 패키지 탐지
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from urllib.parse import quote

import httpx
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# 인기 패키지 목록 (유사도 비교용) - main.py의 목록과 동일하게 유지
POPULAR_PYTHON = {
    "numpy", "pandas", "requests", "flask", "django", "fastapi", "sqlalchemy",
    "pydantic", "celery", "redis", "boto3", "tensorflow", "torch", "pytorch",
    "scikit-learn", "scipy", "matplotlib", "pillow", "cryptography", "aiohttp",
    "httpx", "uvicorn", "gunicorn", "pytest", "click", "typer", "rich",
    "loguru", "pyyaml", "toml", "dotenv", "alembic", "asyncpg", "psycopg2",
    "pymongo", "motor", "elasticsearch", "kafka-python", "celery", "dramatiq",
    "huggingface-hub", "transformers", "diffusers", "langchain", "openai",
    "anthropic", "google-generativeai", "tiktoken", "tokenizers", "datasets",
}

POPULAR_NPM = {
    "react", "react-dom", "next", "vue", "angular", "express", "axios",
    "lodash", "moment", "dayjs", "typescript", "webpack", "vite", "rollup",
    "eslint", "prettier", "jest", "vitest", "playwright", "cypress",
    "tailwindcss", "sass", "styled-components", "zustand", "redux",
    "react-query", "swr", "graphql", "apollo-client", "prisma", "mongoose",
    "sequelize", "typeorm", "socket.io", "ws", "fastify", "koa", "hapi",
    "passport", "jsonwebtoken", "bcrypt", "dotenv", "nodemon", "ts-node",
    "zod", "yup", "joi", "multer", "sharp", "puppeteer", "cheerio",
}


@dataclass
class PackageInfo:
    name: str
    ecosystem: str                      # "python" | "npm" | "both" | "unknown"
    pypi_exists: bool = False
    npm_exists: bool = False
    pypi_upload_date: Optional[str] = None
    npm_publish_date: Optional[str] = None
    days_since_published: Optional[int] = None
    version_count: int = 0
    has_repo_url: bool = False
    has_homepage: bool = False
    has_install_script: bool = False
    risk_score: int = 0
    risk_level: str = "UNKNOWN"
    is_hallucination: bool = False      # 존재하지 않는 패키지
    similar_to: List[str] = field(default_factory=list)
    error: Optional[str] = None


def _days_since(date_str: Optional[str]) -> Optional[int]:
    """ISO 날짜 문자열로부터 현재까지의 일수 계산"""
    if not date_str:
        return None
    try:
        # 다양한 형식 지원
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_str[:19], fmt[:len(date_str[:19])])
                dt = dt.replace(tzinfo=timezone.utc)
                return (datetime.now(timezone.utc) - dt).days
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _find_similar(name: str, popular: set, threshold: int = 85) -> List[str]:
    """편집거리 기반 유사 패키지 탐지"""
    similar = []
    name_lower = name.lower()
    for pop in popular:
        if pop == name_lower:
            continue
        score = fuzz.ratio(name_lower, pop)
        if score >= threshold:
            similar.append(pop)
    return similar[:3]


def _calculate_risk(info: PackageInfo) -> Tuple[int, str]:
    """
    연구용 위험도 판정 — 패키지 존재 여부 중심.
    슬롭스쿼팅 공격 가능성(=할루시네이션 발생 빈도)을 측정하기 위한 점수.
    """
    score = 0

    # 미등록 → 슬롭스쿼팅 공격 표면
    if not info.pypi_exists and not info.npm_exists:
        score += 60
        info.is_hallucination = True

    # 최근 등록 (공격자가 방금 선점했을 가능성)
    if info.days_since_published is not None:
        if info.days_since_published <= 7:
            score += 25
        elif info.days_since_published <= 30:
            score += 15

    # 버전 이력 빈약
    if info.version_count == 1:
        score += 20
    elif info.version_count == 0:
        score += 10

    # 메타데이터 부족
    if not info.has_repo_url:
        score += 15
    if not info.has_homepage:
        score += 5

    # 설치 스크립트 존재
    if info.has_install_script:
        score += 20

    # 유사 패키지 존재 (타이포스쿼팅 의심)
    if info.similar_to:
        score += 15

    final_score = min(score, 100)

    if final_score >= 80:
        level = "CRITICAL"
    elif final_score >= 60:
        level = "HIGH"
    elif final_score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    return final_score, level


async def validate_package(
    name: str,
    client: httpx.AsyncClient,
    pypi_base_url: str = "https://pypi.org/pypi",
    npm_base_url: str = "https://registry.npmjs.org",
    timeout: int = 10,
) -> PackageInfo:
    """단일 패키지를 PyPI + npm 모두 검증"""
    info = PackageInfo(name=name, ecosystem="unknown")

    # ── PyPI 조회 ──────────────────────────────────
    try:
        encoded = quote(name, safe="")
        r = await client.get(f"{pypi_base_url}/{encoded}/json", timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            info.pypi_exists = True
            releases = data.get("releases", {})
            info.version_count = len(releases)

            # 가장 오래된 배포 날짜 찾기
            all_dates = []
            for ver_files in releases.values():
                for f in ver_files:
                    if f.get("upload_time"):
                        all_dates.append(f["upload_time"])
            if all_dates:
                earliest = min(all_dates)
                info.pypi_upload_date = earliest
                info.days_since_published = _days_since(earliest)

            # 메타데이터
            meta = data.get("info", {})
            info.has_repo_url = bool(
                meta.get("project_urls", {}) or meta.get("home_page")
            )
            info.has_homepage = bool(meta.get("home_page"))

            # 유사 패키지
            info.similar_to = _find_similar(name, POPULAR_PYTHON)
    except Exception as e:
        logger.debug(f"PyPI 조회 실패 ({name}): {e}")

    # ── npm 조회 ───────────────────────────────────
    try:
        encoded = quote(name, safe="@/")
        r = await client.get(f"{npm_base_url}/{encoded}", timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            info.npm_exists = True
            versions = data.get("versions", {})
            if info.version_count == 0:
                info.version_count = len(versions)

            # 최초 배포일
            times = data.get("time", {})
            created = times.get("created")
            if created and not info.pypi_upload_date:
                info.npm_publish_date = created
                info.days_since_published = _days_since(created)

            # 메타데이터
            latest_ver = data.get("dist-tags", {}).get("latest", "")
            latest_data = versions.get(latest_ver, {})
            info.has_repo_url = bool(
                data.get("repository") or latest_data.get("repository")
            )
            info.has_homepage = bool(
                data.get("homepage") or latest_data.get("homepage")
            )

            # 설치 스크립트 검사
            scripts = latest_data.get("scripts", {})
            suspicious = {"preinstall", "install", "postinstall"}
            if suspicious & set(scripts.keys()):
                info.has_install_script = True

            # 유사 패키지 (npm쪽도 추가)
            npm_similar = _find_similar(name, POPULAR_NPM)
            info.similar_to = list(set(info.similar_to + npm_similar))[:3]
    except Exception as e:
        logger.debug(f"npm 조회 실패 ({name}): {e}")

    # ── 에코시스템 판정 ────────────────────────────
    if info.pypi_exists and info.npm_exists:
        info.ecosystem = "both"
    elif info.pypi_exists:
        info.ecosystem = "python"
    elif info.npm_exists:
        info.ecosystem = "npm"
    else:
        info.ecosystem = "unknown"

    # ── 위험 점수 ──────────────────────────────────
    info.risk_score, info.risk_level = _calculate_risk(info)

    return info


async def validate_packages_batch(
    names: List[str],
    pypi_base_url: str = "https://pypi.org/pypi",
    npm_base_url: str = "https://registry.npmjs.org",
    concurrency: int = 10,
    timeout: int = 10,
) -> List[PackageInfo]:
    """패키지 목록을 동시에 검증 (동시성 제한 적용)"""
    semaphore = asyncio.Semaphore(concurrency)

    async def _validate_one(name: str, client: httpx.AsyncClient) -> PackageInfo:
        async with semaphore:
            return await validate_package(name, client, pypi_base_url, npm_base_url, timeout)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [_validate_one(name, client) for name in names]
        return await asyncio.gather(*tasks, return_exceptions=False)
