import argparse
import requests
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Step 1에서 복사한 n8n 웹훅 URL (테스트할 때는 webhook-test 주소 사용)
WEBHOOK_URL = "http://host.docker.internal:5679/webhook/slop-check"

def check_code(file_path):
    # 1. 로컬 파일 읽기
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except Exception as e:
        console.print(f"[red]❌ 파일을 읽을 수 없습니다: {e}[/red]")
        sys.exit(1)

    # 2. n8n으로 전송 및 로딩 애니메이션
    with console.status("[bold blue]🤖 n8n AI 슬롭스쿼팅 분석 엔진 가동 중...[/bold blue]"):
        try:
            response = requests.post(WEBHOOK_URL, json={"text": code_content, "source": file_path})
            response.raise_for_status()
            # n8n의 Code 노드 리턴값 구조에 맞춰 JSON 파싱
            n8n_response = response.json()
            # 배열 첫 번째 요소에서 results 가져오기
            result_data = n8n_response[0] if isinstance(n8n_response, list) else n8n_response
            results = result_data.get('results', [])
            
        except requests.exceptions.RequestException as e:
            console.print(f"[red]❌ n8n 서버와 통신 실패: {e}[/red]\n(n8n 워크플로우가 'Listen for Test Event' 상태인지 확인하세요!)")
            sys.exit(1)

    # 3. 결과 출력 (Rich 라이브러리 활용)
    if not results:
        console.print(Panel("[green]✅ 탐지된 패키지가 없거나 코드가 안전해 보입니다![/green]", title="분석 완료"))
        return

    table = Table(title=f"🛡️ AI 슬롭스쿼팅 탐지 결과 ({file_path})", show_header=True, header_style="bold white")
    table.add_column("패키지명", style="cyan", no_wrap=True)
    table.add_column("생태계", justify="center")
    table.add_column("위험도", justify="center")
    table.add_column("점수", justify="right")
    table.add_column("경고 시그널", style="white")

    for r in results:
        level = r.get('level', 'LOW')
        emoji = r.get('emoji', '🟢')
        score = r.get('score', 0)
        
        # 색상 지정
        color = "red" if level == "CRITICAL" else "yellow" if level in ["HIGH", "MEDIUM"] else "green"
        
        # 경고 시그널을 줄바꿈으로 합치기
        signals = "\n".join(r.get('signals', []))
        
        table.add_row(
            r.get('pkg', 'unknown'),
            r.get('pkgEcosystem', 'unknown'),
            f"[{color}]{emoji} {level}[/{color}]",
            f"[{color}]{score}점[/{color}]",
            signals
        )

    console.print(table)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI 환각 패키지(슬롭스쿼팅) 탐지 CLI")
    parser.add_argument("file", help="검사할 소스코드 파일 (예: script.py, package.json)")
    args = parser.parse_args()
    
    check_code(args.file)