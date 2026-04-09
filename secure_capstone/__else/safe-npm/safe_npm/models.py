from dataclasses import dataclass, field
from typing import Any


@dataclass
class PackageInfo:
    name: str
    exists: bool
    latest_version: str | None = None
    published_at: str | None = None
    repository_url: str | None = None
    homepage: str | None = None
    scripts: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskResult:
    package: str
    score: int
    verdict: str  # ALLOW / WARN / BLOCK
    reasons: list[str]
    similar_packages: list[str] = field(default_factory=list)