from pathlib import Path
from rapidfuzz import process, fuzz


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "popular_packages.txt"


def load_popular_packages() -> list[str]:
    if not DATA_FILE.exists():
        return []
    return [line.strip() for line in DATA_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def suggest_similar(package_name: str, limit: int = 5) -> list[str]:
    choices = load_popular_packages()
    if not choices:
        return []

    results = process.extract(
        package_name,
        choices,
        scorer=fuzz.WRatio,
        limit=limit,
    )

    return [name for name, score, _ in results if score >= 60]