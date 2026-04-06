import typer
from rich.table import Table
from safe_npm.registry import fetch_package_info
from safe_npm.risk import analyze_risk
from safe_npm.installer import run_npm_install
from safe_npm.utils import console

app = typer.Typer(help="AI 패키지 추천 검증용 safe-npm CLI")


def print_result(result):
    table = Table(title=f"Inspection Result: {result.package}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Verdict", result.verdict)
    table.add_row("Score", str(result.score))
    table.add_row("Reasons", "\n".join(result.reasons) if result.reasons else "문제 없음")
    table.add_row("Similar", ", ".join(result.similar_packages) if result.similar_packages else "-")

    console.print(table)


@app.command()
def inspect(package_name: str):
    """패키지 검사만 수행"""
    info = fetch_package_info(package_name)
    result = analyze_risk(info)
    print_result(result)

@app.command()
def install(
    package_name: str,
    ignore_scripts: bool = typer.Option(False, help="npm install 시 --ignore-scripts 사용"),
    yes: bool = typer.Option(False, help="경고가 나와도 자동 진행"),
):
    """검사 후 안전하면 설치"""
    info = fetch_package_info(package_name)
    result = analyze_risk(info)
    print_result(result)

    if result.verdict == "BLOCK":
        console.print("[bold red]설치가 차단되었습니다.[/bold red]")
        raise typer.Exit(code=1)

    if result.verdict == "WARN" and not yes:
        proceed = typer.confirm("경고가 있습니다. 계속 설치할까요?")
        if not proceed:
            console.print("설치를 취소했습니다.")
            raise typer.Exit(code=1)

    extra_args = ["--ignore-scripts"] if ignore_scripts else []
    exit_code = run_npm_install(package_name, extra_args=extra_args)

    if exit_code == 0:
        console.print("[bold green]설치가 완료되었습니다.[/bold green]")
    else:
        console.print("[bold red]npm install 실행에 실패했습니다.[/bold red]")
        raise typer.Exit(code=exit_code)
    
