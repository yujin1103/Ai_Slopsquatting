from datetime import datetime, timezone
from safe_npm.models import PackageInfo, RiskResult
from safe_npm.similarity import suggest_similar


SUSPICIOUS_KEYWORDS = [
    "curl ",
    "wget ",
    "powershell",
    "Invoke-WebRequest",
    "bash -c",
    "sh -c",
    "node -e",
    "python -c",
    "eval(",
    "new Function(",
    "child_process",
    "base64",
]


def _days_since(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).days
    except Exception:
        return None


def analyze_risk(info: PackageInfo) -> RiskResult:
    score = 0
    reasons: list[str] = []
    similar = suggest_similar(info.name)

    install_scripts = {}
    if info.scripts:
        install_scripts = {
            k: v for k, v in info.scripts.items()
            if k in ("preinstall", "install", "postinstall")
        }

    # 1. 존재하지 않으면 거의 바로 차단
    if not info.exists:
        score += 60
        reasons.append("패키지가 npm registry에 존재하지 않습니다.")

        if similar:
            score += 20
            reasons.append("유사한 유명 패키지가 존재해 환각/혼동 가능성이 높습니다.")

    else:
        # 2. 최근 생성된 패키지 위험 가중치
        days = _days_since(info.published_at)
        if days is not None:
            if days <= 7:
                score += 25
                reasons.append(f"최신 버전 공개 후 {days}일밖에 지나지 않았습니다.")
            elif days <= 30:
                score += 15
                reasons.append(f"최신 버전 공개 후 {days}일로 매우 최근 패키지입니다.")

        # 3. 메타데이터 부족
        if not info.repository_url:
            score += 15
            reasons.append("repository 정보가 없습니다.")

        if not info.homepage:
            score += 5
            reasons.append("homepage 정보가 없습니다.")

        # 4. 버전 히스토리 짧음
        versions = info.raw.get("versions", {})
        if versions and len(versions) == 1:
            score += 20
            reasons.append("버전 히스토리가 매우 짧습니다.")

        # 5. 이름이 유명 패키지와 유사하면 가중치
        if similar:
            score += 10
            reasons.append("유사한 유명 패키지가 존재합니다.")

        # 6. 설치 스크립트 존재 시 가중치
        if install_scripts:
            score += 20
            reasons.append("설치 시 실행되는 lifecycle script가 존재합니다.")

            joined = " || ".join(install_scripts.values())
            for keyword in SUSPICIOUS_KEYWORDS:
                if keyword.lower() in joined.lower():
                    score += 25
                    reasons.append(f"의심스러운 실행 패턴이 감지되었습니다: {keyword}")
                    break

    # 7. 하드 룰
    hard_block = False

    if not info.exists:
        hard_block = True

    if info.exists and similar and len(info.raw.get("versions", {})) == 1 and not info.repository_url:
        hard_block = True
        reasons.append("신규/단일버전/메타데이터 부족/유사명 조합으로 고위험으로 판단했습니다.")

    if hard_block or score >= 70:
        verdict = "BLOCK"
    elif score >= 30:
        verdict = "WARN"
    else:
        verdict = "ALLOW"

    return RiskResult(
        package=info.name,
        score=score,
        verdict=verdict,
        reasons=reasons,
        similar_packages=similar,
    )