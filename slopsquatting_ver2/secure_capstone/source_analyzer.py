"""
소스코드 정적 분석 모듈
~~~~~~~~~~~~~~~~~~~~~~~
PyPI/npm에 존재하는 패키지의 소스를 다운로드/설치 없이
아카이브를 메모리 스트리밍하여 악성 코드 패턴을 탐지한다.

사용:
    from source_analyzer import analyze_package_source, SourceAnalysisResult
"""

import io
import json as json_mod
import logging
import math
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

MAX_ARCHIVE_SIZE = 5 * 1024 * 1024   # 5 MB
MAX_FILE_SIZE = 512_000               # 500 KB
DOWNLOAD_TIMEOUT = 15.0


# ══════════════════════════════════════════════════════════════════════
# 결과 데이터 클래스
# ══════════════════════════════════════════════════════════════════════

@dataclass
class SourceFinding:
    """소스코드에서 발견된 개별 의심 패턴"""
    category: str           # exec_eval, credential_theft, ...
    description: str        # 사람이 읽을 수 있는 설명
    file_path: str          # 아카이브 내 파일 경로
    matched_text: str       # 매칭된 텍스트 (최대 120자)
    risk_points: int        # 이 카테고리의 점수


@dataclass
class SourceAnalysisResult:
    """소스 분석 전체 결과"""
    analyzed: bool = False
    error: Optional[str] = None
    files_examined: List[str] = field(default_factory=list)
    findings: List[SourceFinding] = field(default_factory=list)
    total_risk_score: int = 0

    @property
    def source_risks(self) -> List[str]:
        return [f.description for f in self.findings]


# ══════════════════════════════════════════════════════════════════════
# 악성 패턴 정의
# ══════════════════════════════════════════════════════════════════════

# (regex_pattern, description, category, risk_points)
PATTERNS: List[Tuple[str, str, str, int]] = [
    # ── install_hook (+20) ───────────────────────────────────
    (r'cmdclass\s*=\s*\{', "setup.py cmdclass 오버라이드 (install 훅 하이재킹)", "install_hook", 20),
    (r'class\s+\w*[Ii]nstall\w*\s*\(.*install\)', "커스텀 install 명령 클래스", "install_hook", 20),

    # ── exec_eval (+15) ──────────────────────────────────────
    (r'\bexec\s*\(', "exec() 호출 탐지", "exec_eval", 15),
    (r'\beval\s*\(', "eval() 호출 탐지", "exec_eval", 15),
    (r'\bcompile\s*\(.*[\'"]exec[\'"]\s*\)', "compile() exec 모드", "exec_eval", 15),
    (r'\bnew\s+Function\s*\(', "new Function() 생성자 (JS)", "exec_eval", 15),

    # ── base64_exec (+25) ────────────────────────────────────
    (r'b64decode\s*\(.*?\).*?exec\s*\(', "base64 디코딩 → exec 조합", "base64_exec", 25),
    (r'exec\s*\(.*?b64decode', "exec 내부에 base64 디코딩", "base64_exec", 25),
    (r'eval\s*\(.*?atob', "eval(atob(...)) 조합 (JS)", "base64_exec", 25),
    (r'atob\s*\(.*?\).*?eval\s*\(', "atob → eval 조합 (JS)", "base64_exec", 25),

    # ── credential_theft (+25) ───────────────────────────────
    (r'(?:os\.environ|os\.getenv|process\.env)[\s\S]{0,500}(?:requests\.post|urllib\.request|http\.client|fetch\s*\(|axios\.post)',
     "환경변수 읽기 + 외부 전송 조합 (인증정보 탈취 의심)", "credential_theft", 25),
    (r'(?:requests\.post|urllib\.request|fetch\s*\(|axios\.post)[\s\S]{0,500}(?:os\.environ|os\.getenv|process\.env)',
     "외부 전송 + 환경변수 읽기 조합 (인증정보 탈취 의심)", "credential_theft", 25),

    # ── shell_execution (+15) ────────────────────────────────
    (r'\bsubprocess\.(?:run|call|Popen|check_output|check_call)\s*\(', "subprocess 실행", "shell_execution", 15),
    (r'\bos\.system\s*\(', "os.system() 호출", "shell_execution", 15),
    (r'\bos\.popen\s*\(', "os.popen() 호출", "shell_execution", 15),
    (r'\bchild_process\b', "child_process 모듈 (Node.js)", "shell_execution", 15),
    (r'\bexecSync\s*\(', "execSync() 호출 (Node.js)", "shell_execution", 15),
    (r'\bspawnSync\s*\(', "spawnSync() 호출 (Node.js)", "shell_execution", 15),
    (r'(?<![a-zA-Z])\bcurl\s+', "curl 명령 사용", "shell_execution", 15),
    (r'(?<![a-zA-Z])\bwget\s+', "wget 명령 사용", "shell_execution", 15),
    (r'\bpowershell\b', "PowerShell 호출", "shell_execution", 15),
    (r'\bbash\s+-c\b', "bash -c 실행", "shell_execution", 15),

    # ── obfuscated_import (+10) ──────────────────────────────
    (r'__import__\s*\(\s*[\'"]os[\'"]\)', "__import__('os') 난독화 import", "obfuscated_import", 10),
    (r'__import__\s*\(\s*[\'"]subprocess[\'"]\)', "__import__('subprocess') 난독화 import", "obfuscated_import", 10),
    (r'__import__\s*\(\s*[\'"]socket[\'"]\)', "__import__('socket') 난독화 import", "obfuscated_import", 10),
    (r'__import__\s*\(\s*[\'"]shutil[\'"]\)', "__import__('shutil') 난독화 import", "obfuscated_import", 10),
    (r'getattr\s*\(\s*__import__', "getattr(__import__()) 체인", "obfuscated_import", 10),

    # ── network_access (+10) ─────────────────────────────────
    (r'\bsocket\.socket\s*\(', "raw 소켓 생성", "network_access", 10),
    (r'\burllib\.request\.urlopen\s*\(', "urllib.request.urlopen() 호출", "network_access", 10),
    (r'\bhttp\.client\.HTTP', "http.client 직접 사용", "network_access", 10),
]

# npm install script 전용 패턴 (package.json scripts 필드 검사)
NPM_SCRIPT_PATTERNS: List[Tuple[str, str]] = [
    (r'\bcurl\s', "install script 내 curl 사용"),
    (r'\bwget\s', "install script 내 wget 사용"),
    (r'\bpowershell\b', "install script 내 PowerShell 사용"),
    (r'Invoke-WebRequest', "install script 내 Invoke-WebRequest"),
    (r'\bbash\s+-c\b', "install script 내 bash -c 실행"),
    (r'\bnode\s+-e\b', "install script 내 node -e 실행"),
    (r'\bpython\s+-c\b', "install script 내 python -c 실행"),
    (r'\beval\s*\(', "install script 내 eval() 사용"),
]

# 추출 대상 파일명
PYTHON_CRITICAL_FILES = {"setup.py", "setup.cfg", "pyproject.toml", "__init__.py", "__main__.py"}
NPM_CRITICAL_FILES = {"package.json", "index.js", "index.mjs", "install.js", "preinstall.js", "postinstall.js"}


# ══════════════════════════════════════════════════════════════════════
# 공개 API
# ══════════════════════════════════════════════════════════════════════

async def analyze_package_source(
    name: str,
    ecosystem: str,
    registry_data: dict,
    client: httpx.AsyncClient,
    timeout: float = DOWNLOAD_TIMEOUT,
    max_size: int = MAX_ARCHIVE_SIZE,
) -> SourceAnalysisResult:
    """
    패키지 소스코드를 메모리 스트리밍으로 분석.
    registry_data는 PyPI/npm JSON API 응답 원본.
    """
    try:
        if ecosystem in ("python", "both"):
            return await _analyze_pypi_source(name, registry_data, client, timeout, max_size)
        elif ecosystem == "npm":
            return await _analyze_npm_source(name, registry_data, client, timeout, max_size)
        else:
            return SourceAnalysisResult(analyzed=False, error="알 수 없는 에코시스템")
    except Exception as e:
        logger.debug(f"소스 분석 실패 ({name}): {e}")
        return SourceAnalysisResult(analyzed=False, error=str(e)[:200])


# ══════════════════════════════════════════════════════════════════════
# PyPI 소스 분석
# ══════════════════════════════════════════════════════════════════════

async def _analyze_pypi_source(
    name: str,
    registry_data: dict,
    client: httpx.AsyncClient,
    timeout: float,
    max_size: int,
) -> SourceAnalysisResult:
    """PyPI 패키지의 소스 아카이브를 분석"""
    url_info = _get_pypi_archive_url(registry_data)
    if not url_info:
        return SourceAnalysisResult(analyzed=False, error="아카이브 URL을 찾을 수 없음")

    url, fmt = url_info
    archive_bytes = await _download_archive(url, client, timeout, max_size)
    if archive_bytes is None:
        return SourceAnalysisResult(analyzed=False, error="아카이브 다운로드 실패 또는 크기 초과")

    # 파일 추출
    if fmt == "whl":
        files = _extract_critical_files_wheel(archive_bytes)
    else:
        files = _extract_critical_files_tar(archive_bytes, "python")

    if not files:
        return SourceAnalysisResult(analyzed=True, files_examined=[], error="추출 가능한 파일 없음")

    # 패턴 스캔
    all_findings: List[SourceFinding] = []
    for fpath, content in files.items():
        findings = _scan_file_content(fpath, content, "python")
        all_findings.extend(findings)

    deduped, total_score = _deduplicate_findings(all_findings)
    return SourceAnalysisResult(
        analyzed=True,
        files_examined=list(files.keys()),
        findings=deduped,
        total_risk_score=total_score,
    )


# ══════════════════════════════════════════════════════════════════════
# npm 소스 분석
# ══════════════════════════════════════════════════════════════════════

async def _analyze_npm_source(
    name: str,
    registry_data: dict,
    client: httpx.AsyncClient,
    timeout: float,
    max_size: int,
) -> SourceAnalysisResult:
    """npm 패키지의 tarball을 분석"""
    # 먼저 package.json scripts 필드 검사 (tarball 다운로드 없이)
    script_findings = _check_npm_scripts(registry_data)

    url = _get_npm_tarball_url(registry_data)
    if not url:
        # scripts 검사 결과만 반환
        if script_findings:
            deduped, total_score = _deduplicate_findings(script_findings)
            return SourceAnalysisResult(
                analyzed=True, findings=deduped, total_risk_score=total_score,
            )
        return SourceAnalysisResult(analyzed=False, error="tarball URL을 찾을 수 없음")

    archive_bytes = await _download_archive(url, client, timeout, max_size)
    if archive_bytes is None:
        # tarball 실패해도 scripts 결과 반환
        if script_findings:
            deduped, total_score = _deduplicate_findings(script_findings)
            return SourceAnalysisResult(
                analyzed=True, findings=deduped, total_risk_score=total_score,
            )
        return SourceAnalysisResult(analyzed=False, error="tarball 다운로드 실패 또는 크기 초과")

    files = _extract_critical_files_tar(archive_bytes, "npm")
    all_findings: List[SourceFinding] = list(script_findings)

    for fpath, content in files.items():
        findings = _scan_file_content(fpath, content, "npm")
        all_findings.extend(findings)

    deduped, total_score = _deduplicate_findings(all_findings)
    return SourceAnalysisResult(
        analyzed=True,
        files_examined=list(files.keys()),
        findings=deduped,
        total_risk_score=total_score,
    )


# ══════════════════════════════════════════════════════════════════════
# 아카이브 URL 추출
# ══════════════════════════════════════════════════════════════════════

def _get_pypi_archive_url(registry_data: dict) -> Optional[Tuple[str, str]]:
    """PyPI JSON에서 최신 버전의 소스 아카이브 URL 추출. (url, format) 반환."""
    latest_ver = registry_data.get("info", {}).get("version")
    if not latest_ver:
        return None

    files = registry_data.get("releases", {}).get(latest_ver, [])

    # .tar.gz (sdist) 우선
    for f in files:
        fname = f.get("filename", "")
        if fname.endswith(".tar.gz"):
            return (f["url"], "tar.gz")

    # .whl 폴백
    for f in files:
        fname = f.get("filename", "")
        if fname.endswith(".whl"):
            return (f["url"], "whl")

    return None


def _get_npm_tarball_url(registry_data: dict) -> Optional[str]:
    """npm 레지스트리 JSON에서 최신 tarball URL 추출."""
    latest_ver = registry_data.get("dist-tags", {}).get("latest")
    if not latest_ver:
        return None
    ver_data = registry_data.get("versions", {}).get(latest_ver, {})
    return ver_data.get("dist", {}).get("tarball")


# ══════════════════════════════════════════════════════════════════════
# 아카이브 다운로드 (메모리 스트리밍)
# ══════════════════════════════════════════════════════════════════════

async def _download_archive(
    url: str,
    client: httpx.AsyncClient,
    timeout: float,
    max_size: int,
) -> Optional[bytes]:
    """아카이브를 메모리로 스트리밍. 크기 초과 시 None 반환."""
    try:
        async with client.stream("GET", url, timeout=timeout) as resp:
            if resp.status_code != 200:
                logger.debug(f"아카이브 HTTP {resp.status_code}: {url}")
                return None

            # Content-Length 사전 검사
            cl = resp.headers.get("content-length")
            if cl and int(cl) > max_size:
                logger.debug(f"아카이브 크기 초과 ({cl} bytes): {url}")
                return None

            # 스트리밍 수집
            chunks = bytearray()
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                chunks.extend(chunk)
                if len(chunks) > max_size:
                    logger.debug(f"스트리밍 중 크기 초과: {url}")
                    return None

            return bytes(chunks)

    except httpx.TimeoutException:
        logger.debug(f"아카이브 다운로드 타임아웃: {url}")
        return None
    except Exception as e:
        logger.debug(f"아카이브 다운로드 오류: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════
# 파일 추출
# ══════════════════════════════════════════════════════════════════════

def _extract_critical_files_tar(
    archive_bytes: bytes,
    ecosystem: str,
) -> Dict[str, str]:
    """tar.gz / tgz 아카이브에서 핵심 파일만 추출. {경로: 내용} 반환."""
    critical = PYTHON_CRITICAL_FILES if ecosystem == "python" else NPM_CRITICAL_FILES
    result: Dict[str, str] = {}

    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile() or member.size > MAX_FILE_SIZE:
                    continue

                basename = member.name.split("/")[-1]
                if basename in critical:
                    f = tar.extractfile(member)
                    if f:
                        try:
                            content = f.read().decode("utf-8", errors="replace")
                            result[member.name] = content
                        except Exception:
                            pass
    except (tarfile.TarError, EOFError, Exception) as e:
        logger.debug(f"tar 추출 오류: {e}")

    return result


def _extract_critical_files_wheel(archive_bytes: bytes) -> Dict[str, str]:
    """.whl (zip) 아카이브에서 핵심 파일만 추출."""
    result: Dict[str, str] = {}

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size > MAX_FILE_SIZE:
                    continue

                basename = info.filename.split("/")[-1]
                if basename in PYTHON_CRITICAL_FILES:
                    try:
                        content = zf.read(info.filename).decode("utf-8", errors="replace")
                        result[info.filename] = content
                    except Exception:
                        pass
    except (zipfile.BadZipFile, Exception) as e:
        logger.debug(f"wheel 추출 오류: {e}")

    return result


# ══════════════════════════════════════════════════════════════════════
# 패턴 스캔
# ══════════════════════════════════════════════════════════════════════

def _scan_file_content(
    file_path: str,
    content: str,
    ecosystem: str,
) -> List[SourceFinding]:
    """단일 파일에 대해 모든 악성 패턴을 검사."""
    findings: List[SourceFinding] = []

    for pattern, desc, category, points in PATTERNS:
        try:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                matched = match.group(0)[:120]
                findings.append(SourceFinding(
                    category=category,
                    description=desc,
                    file_path=file_path,
                    matched_text=matched,
                    risk_points=points,
                ))
        except re.error:
            pass

    # 고엔트로피 문자열 탐지
    entropy_findings = _scan_high_entropy_strings(file_path, content)
    findings.extend(entropy_findings)

    return findings


def _check_npm_scripts(registry_data: dict) -> List[SourceFinding]:
    """npm 레지스트리 JSON에서 lifecycle scripts의 악성 패턴 검사."""
    findings: List[SourceFinding] = []

    latest_ver = registry_data.get("dist-tags", {}).get("latest")
    if not latest_ver:
        return findings

    ver_data = registry_data.get("versions", {}).get(latest_ver, {})
    scripts = ver_data.get("scripts", {})

    suspicious_keys = {"preinstall", "install", "postinstall"}
    for key in suspicious_keys & set(scripts.keys()):
        script_content = scripts[key]
        if not isinstance(script_content, str):
            continue

        for pattern, desc in NPM_SCRIPT_PATTERNS:
            try:
                match = re.search(pattern, script_content, re.IGNORECASE)
                if match:
                    findings.append(SourceFinding(
                        category="npm_install_script",
                        description=f"{desc} ({key})",
                        file_path="package.json",
                        matched_text=match.group(0)[:120],
                        risk_points=25,
                    ))
            except re.error:
                pass

    return findings


# ══════════════════════════════════════════════════════════════════════
# 고엔트로피 문자열 탐지
# ══════════════════════════════════════════════════════════════════════

_HIGH_ENTROPY_RE = re.compile(r'[\'\"]([^\'\"\n]{50,})[\'\"]')


def _calculate_entropy(s: str) -> float:
    """Shannon 엔트로피 계산."""
    if not s:
        return 0.0
    freq: Dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _scan_high_entropy_strings(file_path: str, content: str) -> List[SourceFinding]:
    """50자 이상 문자열 리터럴 중 엔트로피가 높은 것을 탐지."""
    findings: List[SourceFinding] = []

    for match in _HIGH_ENTROPY_RE.finditer(content):
        s = match.group(1)
        entropy = _calculate_entropy(s)
        if entropy > 4.5:
            findings.append(SourceFinding(
                category="high_entropy_string",
                description=f"고엔트로피 문자열 탐지 (엔트로피: {entropy:.2f}, 길이: {len(s)}자)",
                file_path=file_path,
                matched_text=s[:120],
                risk_points=10,
            ))
            break  # 파일당 최대 1개

    return findings


# ══════════════════════════════════════════════════════════════════════
# 결과 집계
# ══════════════════════════════════════════════════════════════════════

def _deduplicate_findings(
    findings: List[SourceFinding],
) -> Tuple[List[SourceFinding], int]:
    """
    카테고리별 중복 제거 후 총 점수 계산.
    - 모든 findings는 보존 (리포트용)
    - 점수는 카테고리당 최대 1회만 합산
    - 총점은 100 상한
    """
    if not findings:
        return [], 0

    # 카테고리별 최고 점수만 합산
    category_max: Dict[str, int] = {}
    for f in findings:
        if f.category not in category_max or f.risk_points > category_max[f.category]:
            category_max[f.category] = f.risk_points

    total = min(sum(category_max.values()), 100)
    return findings, total
