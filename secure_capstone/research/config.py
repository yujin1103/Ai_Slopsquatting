"""
환경변수 기반 설정 관리
.env 파일 또는 시스템 환경변수에서 로드
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # ── LLM API 키 ──────────────────────────────────
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))

    # ── 사용할 모델 ──────────────────────────────────
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o"))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))
    google_model: str = field(default_factory=lambda: os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"))

    # ── 실험 파라미터 ────────────────────────────────
    runs_per_question: int = field(default_factory=lambda: int(os.getenv("RUNS_PER_QUESTION", "5")))
    max_packages_per_response: int = field(default_factory=lambda: int(os.getenv("MAX_PACKAGES_PER_RESPONSE", "8")))

    # ── 동시성 / 속도 제한 ───────────────────────────
    llm_concurrency: int = field(default_factory=lambda: int(os.getenv("LLM_CONCURRENCY", "3")))
    validation_concurrency: int = field(default_factory=lambda: int(os.getenv("VALIDATION_CONCURRENCY", "10")))
    request_delay_seconds: float = field(default_factory=lambda: float(os.getenv("REQUEST_DELAY_SECONDS", "1.0")))

    # ── 경로 설정 ────────────────────────────────────
    db_path: str = field(default_factory=lambda: os.getenv(
        "DB_PATH",
        os.path.join(os.path.dirname(__file__), "results", "slopsquatting_research.db")
    ))
    report_dir: str = field(default_factory=lambda: os.getenv(
        "REPORT_DIR",
        os.path.join(os.path.dirname(__file__), "results", "reports")
    ))

    # ── PyPI / npm API ───────────────────────────────
    pypi_base_url: str = "https://pypi.org/pypi"
    npm_base_url: str = "https://registry.npmjs.org"
    api_timeout_seconds: int = 10

    def enabled_models(self) -> List[str]:
        """API 키가 설정된 모델만 반환"""
        models = []
        if self.openai_api_key:
            models.append("gpt-4o")
        if self.anthropic_api_key:
            models.append("claude-3-5-sonnet")
        if self.google_api_key:
            models.append("gemini-2.0-flash")
        return models

    def validate(self) -> None:
        """최소 하나의 LLM API 키가 있는지 확인"""
        if not self.enabled_models():
            raise ValueError(
                "최소 하나의 LLM API 키가 필요합니다.\n"
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY 중 하나를 .env에 설정하세요."
            )

    def ensure_dirs(self) -> None:
        """결과 저장 디렉토리 생성"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.report_dir, exist_ok=True)


# 싱글톤
config = Config()
