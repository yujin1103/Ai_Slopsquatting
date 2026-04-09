from pathlib import Path
from rapidfuzz import process, fuzz


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "popular_packages.txt"


def load_popular_packages() -> list[str]:
    if not DATA_FILE.exists():
        return []

    return [
        line.strip()
        for line in DATA_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def suggest_similar(package_name: str, limit: int = 5) -> list[str]:
    choices = load_popular_packages()
    if not choices:
        return []

    results = process.extract(
        package_name,
        choices,
        scorer=fuzz.WRatio,
        limit=limit + 3,
    )

    normalized = package_name.strip().lower()
    filtered: list[str] = []

    for name, score, _ in results:
        if name.strip().lower() == normalized:
            continue
        if score < 70:
            continue
        filtered.append(name)

    return filtered[:limit]