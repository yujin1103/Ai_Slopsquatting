"""
slop_check.py  —  AI 슬롭스쿼팅 탐지 CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
사용법:
  python slop_check.py <파일경로>

예시:
  python slop_check.py danger_test.py
  python slop_check.py ../frontend/index.ts
  python slop_check.py package.json

환경변수:
  SLOP_API_URL  FastAPI 서버 주소 (기본: http://localhost:8001)
                Docker 내부에서 호출 시: http://slop-api:8001
"""

import argparse
import os
import sys

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# FastAPI 직접 호출 (n8n 우회 — AST 하이브리드 파서 사용)
API_URL = os.environ.get("SLOP_API_URL", "http://localhost:8001")
PARSE_AND_ANALYZE_URL = f"{API_URL}/parse-and-analyze"

# 위험 레벨별 색상·이모지 매핑
_LEVEL_STYLE: dict[str, tuple[str, str]] = {
    "CRITICAL": ("red",    "🔴"),
    "HIGH":     ("yellow", "🟠"),
    "MEDIUM":   ("yellow", "🟡"),
    "LOW":      ("green",  "🟢"),
}

# 파싱 방법 설명
_METHOD_LABEL: dict[str, str] = {
    "ast":     "AST (정적 분석)",
    "regex":   "Regex (동적 패턴)",
    "hybrid":  "AST + Regex (하이브리드)",
    "json":    "JSON 파싱",
}


def check_code(file_path: str) -> None:
    # ── 1. 파일 읽기 ──────────────────────────────────────────────────────────
    try:
        with open(file_path, encoding="utf-8") as f:
            code_content = f.read()
    except Exception as e:
        console.print(f"[red]❌ 파일을 읽을 수 없습니다: {e}[/red]")
        sys.exit(1)

    filename = os.path.basename(file_path)

    # ── 2. FastAPI /parse-and-analyze 호출 ────────────────────────────────────
    with console.status("[bold blue]🤖 AST 하이브리드 슬롭스쿼팅 분석 중...[/bold blue]"):
        try:
            response = requests.post(
                PARSE_AND_ANALYZE_URL,
                json={"filename": filename, "code": code_content},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.ConnectionError:
            console.print(
                f"[red]❌ API 서버에 연결할 수 없습니다: {API_URL}\n"
                "Docker가 실행 중인지 확인하거나 SLOP_API_URL 환경변수를 설정하세요.[/red]"
            )
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ API 요청 실패: {e}[/red]")
            sys.exit(1)

    results: list[dict] = data.get("results", [])
    language: str       = data.get("language", "unknown")
    parse_method: str   = data.get("parse_method", "unknown")
    static_count: int   = data.get("static_count", 0)
    dynamic_count: int  = data.get("dynamic_count", 0)

    # ── 3. 파싱 요약 패널 ─────────────────────────────────────────────────────
    method_label = _METHOD_LABEL.get(parse_method, parse_method)
    summary_lines = [
        f"[bold]파일[/bold]: {file_path}",
        f"[bold]언어[/bold]: {language}",
        f"[bold]파싱 방법[/bold]: {method_label}",
        f"[bold]정적 import[/bold]: {static_count}개  "
        f"[bold]동적 import[/bold]: {dynamic_count}개",
    ]
    console.print(Panel("\n".join(summary_lines), title="📂 파싱 결과", border_style="blue"))

    # ── 4. 탐지 결과 없음 ─────────────────────────────────────────────────────
    if not results:
        console.print(
            Panel(
                "[green]✅ 탐지된 외부 패키지가 없거나 모두 안전해 보입니다![/green]",
                title="분석 완료",
            )
        )
        return

    # ── 5. 결과 테이블 출력 ───────────────────────────────────────────────────
    table = Table(
        title=f"🛡️ AI 슬롭스쿼팅 탐지 결과 — {filename}",
        show_header=True,
        header_style="bold white",
        show_lines=True,
    )
    table.add_column("패키지명",   style="cyan",  no_wrap=True)
    table.add_column("방식",       justify="center", width=8)
    table.add_column("에코시스템", justify="center", width=10)
    table.add_column("위험도",     justify="center", width=12)
    table.add_column("점수",       justify="right",  width=6)
    table.add_column("경고 시그널", style="white")

    for r in results:
        level   = r.get("level", "LOW")
        color, emoji = _LEVEL_STYLE.get(level, ("green", "🟢"))
        score   = r.get("score", 0)
        pkg     = r.get("package", "unknown")
        eco     = r.get("ecosystem", "unknown")
        dynamic = r.get("is_dynamic", False)
        signals = "\n".join(r.get("signals", []))

        import_badge = "[magenta]동적[/magenta]" if dynamic else "[blue]정적[/blue]"
        eco_display  = {
            "python":  "🐍 Python",
            "npm":     "📦 npm",
            "both":    "🐍📦 Both",
            "unknown": "❓ 미확인",
        }.get(eco, eco)

        table.add_row(
            pkg,
            import_badge,
            eco_display,
            f"[{color}]{emoji} {level}[/{color}]",
            f"[{color}]{score}점[/{color}]",
            signals,
        )

    console.print(table)

    # ── 6. 위험 패키지 요약 ───────────────────────────────────────────────────
    dangerous = [r for r in results if r.get("level") in ("CRITICAL", "HIGH")]
    if dangerous:
        pkg_list = ", ".join(f"[red]{r['package']}[/red]" for r in dangerous)
        console.print(
            Panel(
                f"⚠️  HIGH 이상 위험 패키지 {len(dangerous)}개 발견: {pkg_list}\n"
                "즉시 제거하거나 공식 패키지로 교체하세요.",
                title="🚨 보안 경고",
                border_style="red",
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI 환각 패키지(슬롭스쿼팅) 탐지 CLI")
    parser.add_argument("file", help="검사할 소스코드 파일 (예: script.py, index.ts, package.json)")
    args = parser.parse_args()
    check_code(args.file)
