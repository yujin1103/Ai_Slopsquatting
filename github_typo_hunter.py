import time
import requests
import csv
import os

# 1. 설정
GITHUB_TOKEN = "여기에_발급받은_토큰_입력"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
POPULAR_PKGS_PATH = "api/data/popular_python_packages.txt" # 팀의 인기 패키지 목록 경로
OUTPUT_CSV = "github_typo_report.csv"

def generate_typos(pkg_name):
    """
    패키지명의 흔한 오타(Typo) 리스트를 생성합니다.
    """
    typos = set()
    
    # 1. 하이픈(-)과 언더바(_) 혼동 (가장 흔한 케이스)
    if "-" in pkg_name:
        typos.add(pkg_name.replace("-", "_"))
    if "_" in pkg_name:
        typos.add(pkg_name.replace("_", "-"))
        
    # 2. 글자 순서 바뀜 (예: requests -> requsets)
    if len(pkg_name) > 3:
        for i in range(1, len(pkg_name) - 1):
            typo = list(pkg_name)
            typo[i], typo[i+1] = typo[i+1], typo[i]
            typos.add("".join(typo))
            
    # 원본 이름은 제외
    if pkg_name in typos:
        typos.remove(pkg_name)
    return list(typos)

def search_github_for_typo(typo_name):
    """
    깃허브 코드에서 해당 오타 패키지를 임포트/설치하려는 시도가 있는지 검색합니다.
    """
    # requirements.txt에 적힌 경우 또는 코드에서 import 하는 경우 검색
    query = f'"{typo_name}" in:file language:python'
    url = f"https://api.github.com/search/code?q={query}"
    
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        return data.get("total_count", 0)
    elif response.status_code == 403:
        print("API 호출 한도 초과! 60초 대기...")
        time.sleep(60)
        return search_github_for_typo(typo_name)
    return 0

def check_pypi_exists(pkg_name):
    """
    해당 이름이 실제 PyPI에 악성 패키지(또는 실수)로 등록되어 있는지 확인합니다.
    """
    url = f"https://pypi.org/pypi/{pkg_name}/json"
    response = requests.get(url)
    return response.status_code == 200

def main():
    print("🎯 깃허브 오타 사냥(Typo Hunter) 시작...")
    
    # 인기 패키지 로드 (없을 경우를 대비해 예시 데이터 추가)
    if os.path.exists(POPULAR_PKGS_PATH):
        with open(POPULAR_PKGS_PATH, "r", encoding="utf-8") as f:
            popular_packages = [line.strip() for line in f if line.strip()]
    else:
        print(f"경고: {POPULAR_PKGS_PATH} 가 없습니다. 테스트용 목록을 사용합니다.")
        popular_packages = ["requests", "python-dotenv", "scikit-learn", "flask"]

    results = []
    
    # 테스트를 위해 상위 10개만 먼저 실행 (전체 실행 시 시간 소요)
    for original_pkg in popular_packages[:10]:
        typos = generate_typos(original_pkg)
        
        for typo in typos:
            print(f"검색 중: [{original_pkg}]의 오타 -> '{typo}'")
            
            # 깃허브 검색 (Rate Limit 방지를 위해 2초 대기)
            github_hits = search_github_for_typo(typo)
            time.sleep(2) 
            
            if github_hits > 0:
                print(f"  👉 깃허브에서 {github_hits}건 발견!")
                pypi_exists = check_pypi_exists(typo)
                
                results.append({
                    "Original Package": original_pkg,
                    "Typo Package": typo,
                    "GitHub Occurrences": github_hits,
                    "Exists on PyPI (DANGER)": pypi_exists
                })
                
                if pypi_exists:
                    print(f"  🚨 [경고] PyPI에도 존재함! 누군가 이 오타를 선점했습니다!")

    # 결과를 CSV로 저장
    if results:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["Original Package", "Typo Package", "GitHub Occurrences", "Exists on PyPI (DANGER)"])
            writer.writeheader()
            writer.writerows(results)
        print(f"\n✅ 스캔 완료! '{OUTPUT_CSV}' 파일이 생성되었습니다.")
    else:
        print("\n✅ 스캔 완료! 발견된 위협 데이터가 없습니다.")

if __name__ == "__main__":
    main()