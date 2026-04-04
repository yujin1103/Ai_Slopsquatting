"""
SQLite 데이터베이스 모듈
- 실험 결과 영구 저장
- 재실행 시 이미 처리된 항목 스킵 (resumable)
- 분석용 쿼리 메서드 제공
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SCHEMA = """
-- LLM 응답 원본 저장
CREATE TABLE IF NOT EXISTS experiments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id     INTEGER NOT NULL,
    question_text   TEXT    NOT NULL,
    domain          TEXT    NOT NULL,
    model_name      TEXT    NOT NULL,
    run_number      INTEGER NOT NULL,
    raw_response    TEXT,
    tokens_used     INTEGER DEFAULT 0,
    latency_ms      INTEGER DEFAULT 0,
    error           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(question_id, model_name, run_number)
);

-- 추출 + 검증된 패키지 결과
CREATE TABLE IF NOT EXISTS packages (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id        INTEGER NOT NULL REFERENCES experiments(id),
    question_id          INTEGER NOT NULL,
    domain               TEXT    NOT NULL,
    model_name           TEXT    NOT NULL,
    package_name         TEXT    NOT NULL,
    ecosystem            TEXT,
    pypi_exists          INTEGER DEFAULT 0,
    npm_exists           INTEGER DEFAULT 0,
    pypi_upload_date     TEXT,
    npm_publish_date     TEXT,
    days_since_published INTEGER,
    version_count        INTEGER DEFAULT 0,
    has_repo_url         INTEGER DEFAULT 0,
    has_homepage         INTEGER DEFAULT 0,
    has_install_script   INTEGER DEFAULT 0,
    risk_score           INTEGER DEFAULT 0,
    risk_level           TEXT,
    is_hallucination     INTEGER DEFAULT 0,
    similar_to           TEXT,   -- JSON 배열
    created_at           TEXT DEFAULT (datetime('now'))
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_packages_hallucination ON packages(is_hallucination);
CREATE INDEX IF NOT EXISTS idx_packages_model ON packages(model_name);
CREATE INDEX IF NOT EXISTS idx_packages_domain ON packages(domain);
CREATE INDEX IF NOT EXISTS idx_packages_name ON packages(package_name);
CREATE INDEX IF NOT EXISTS idx_experiments_model ON experiments(model_name);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)
        logger.info(f"DB 초기화 완료: {self.db_path}")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── 쓰기 ──────────────────────────────────────

    def save_experiment(
        self,
        question_id: int,
        question_text: str,
        domain: str,
        model_name: str,
        run_number: int,
        raw_response: str,
        tokens_used: int,
        latency_ms: int,
        error: Optional[str],
    ) -> Optional[int]:
        """experiment 저장 후 ID 반환. 이미 존재하면 None 반환"""
        with self._conn() as conn:
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO experiments
                       (question_id, question_text, domain, model_name, run_number,
                        raw_response, tokens_used, latency_ms, error)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (question_id, question_text, domain, model_name, run_number,
                     raw_response, tokens_used, latency_ms, error),
                )
                if cur.lastrowid and cur.rowcount > 0:
                    return cur.lastrowid
                # 이미 존재하는 경우 ID 조회
                row = conn.execute(
                    "SELECT id FROM experiments WHERE question_id=? AND model_name=? AND run_number=?",
                    (question_id, model_name, run_number)
                ).fetchone()
                return row["id"] if row else None
            except sqlite3.IntegrityError:
                return None

    def save_packages(
        self,
        experiment_id: int,
        question_id: int,
        domain: str,
        model_name: str,
        packages: list,  # List[PackageInfo]
    ) -> int:
        """패키지 목록 저장. 저장된 개수 반환"""
        if not packages:
            return 0
        rows = []
        for p in packages:
            rows.append((
                experiment_id, question_id, domain, model_name,
                p.name, p.ecosystem,
                int(p.pypi_exists), int(p.npm_exists),
                p.pypi_upload_date, p.npm_publish_date,
                p.days_since_published, p.version_count,
                int(p.has_repo_url), int(p.has_homepage), int(p.has_install_script),
                p.risk_score, p.risk_level,
                int(p.is_hallucination),
                json.dumps(p.similar_to),
            ))
        with self._conn() as conn:
            conn.executemany(
                """INSERT INTO packages
                   (experiment_id, question_id, domain, model_name,
                    package_name, ecosystem,
                    pypi_exists, npm_exists,
                    pypi_upload_date, npm_publish_date,
                    days_since_published, version_count,
                    has_repo_url, has_homepage, has_install_script,
                    risk_score, risk_level,
                    is_hallucination, similar_to)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
        return len(rows)

    # ── 읽기 ──────────────────────────────────────

    def is_already_done(self, question_id: int, model_name: str, run_number: int) -> bool:
        """해당 (질문, 모델, 실행 번호) 조합이 이미 처리됐는지 확인"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM experiments WHERE question_id=? AND model_name=? AND run_number=?",
                (question_id, model_name, run_number)
            ).fetchone()
            return row is not None

    def get_progress(self) -> Dict:
        """전체 진행 현황 요약"""
        with self._conn() as conn:
            total_exp = conn.execute("SELECT COUNT(*) as c FROM experiments").fetchone()["c"]
            total_pkg = conn.execute("SELECT COUNT(*) as c FROM packages").fetchone()["c"]
            hallucinations = conn.execute(
                "SELECT COUNT(*) as c FROM packages WHERE is_hallucination=1"
            ).fetchone()["c"]
            model_counts = conn.execute(
                "SELECT model_name, COUNT(*) as c FROM experiments GROUP BY model_name"
            ).fetchall()
        return {
            "total_experiments": total_exp,
            "total_packages": total_pkg,
            "hallucinations": hallucinations,
            "hallucination_rate": round(hallucinations / total_pkg * 100, 2) if total_pkg > 0 else 0,
            "model_counts": {r["model_name"]: r["c"] for r in model_counts},
        }

    def get_hallucination_stats(self) -> Dict:
        """모델별 / 도메인별 할루시네이션 통계"""
        with self._conn() as conn:
            # 모델별
            model_stats = conn.execute("""
                SELECT model_name,
                       COUNT(*) as total,
                       SUM(is_hallucination) as hallucinations,
                       ROUND(100.0 * SUM(is_hallucination) / COUNT(*), 2) as rate
                FROM packages
                GROUP BY model_name
                ORDER BY rate DESC
            """).fetchall()

            # 도메인별
            domain_stats = conn.execute("""
                SELECT domain,
                       COUNT(*) as total,
                       SUM(is_hallucination) as hallucinations,
                       ROUND(100.0 * SUM(is_hallucination) / COUNT(*), 2) as rate
                FROM packages
                GROUP BY domain
                ORDER BY rate DESC
            """).fetchall()

            # 반복 할루시네이션 (여러 모델에서 동시 등장)
            repeated = conn.execute("""
                SELECT package_name,
                       COUNT(DISTINCT model_name) as model_count,
                       COUNT(*) as total_mentions
                FROM packages
                WHERE is_hallucination=1
                GROUP BY package_name
                HAVING model_count >= 2
                ORDER BY model_count DESC, total_mentions DESC
                LIMIT 50
            """).fetchall()

        return {
            "by_model": [dict(r) for r in model_stats],
            "by_domain": [dict(r) for r in domain_stats],
            "high_risk_repeated": [dict(r) for r in repeated],
        }

    def get_risk_distribution(self) -> Dict:
        """위험 레벨 분포"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT risk_level, COUNT(*) as count
                FROM packages
                GROUP BY risk_level
                ORDER BY count DESC
            """).fetchall()
        return {r["risk_level"]: r["count"] for r in rows}

    def get_top_hallucinated_packages(self, limit: int = 30) -> List[Dict]:
        """가장 많이 할루시네이션된 패키지 목록"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT package_name,
                       domain,
                       COUNT(*) as mention_count,
                       COUNT(DISTINCT model_name) as model_count,
                       COUNT(DISTINCT question_id) as question_count,
                       GROUP_CONCAT(DISTINCT model_name) as models
                FROM packages
                WHERE is_hallucination=1
                GROUP BY package_name
                ORDER BY mention_count DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def export_all(self) -> Tuple[List[Dict], List[Dict]]:
        """전체 데이터 내보내기 (분석용)"""
        with self._conn() as conn:
            experiments = [dict(r) for r in conn.execute("SELECT * FROM experiments").fetchall()]
            packages = [dict(r) for r in conn.execute("SELECT * FROM packages").fetchall()]
        return experiments, packages

    def get_full_qa_data(self) -> List[Dict]:
        """질문-답변 전체 데이터를 JSON 리포트용으로 반환.
        각 experiment에 대해 질문, LLM 원본 응답, 추출된 패키지 검증 결과를 포함."""
        with self._conn() as conn:
            experiments = conn.execute("""
                SELECT id, question_id, question_text, domain, model_name,
                       run_number, raw_response, tokens_used, latency_ms,
                       error, created_at
                FROM experiments
                ORDER BY question_id, model_name, run_number
            """).fetchall()

            results = []
            for exp in experiments:
                exp_dict = dict(exp)
                exp_id = exp_dict["id"]

                # 해당 experiment의 패키지 검증 결과
                pkgs = conn.execute("""
                    SELECT package_name, ecosystem, pypi_exists, npm_exists,
                           pypi_upload_date, npm_publish_date, days_since_published,
                           version_count, has_repo_url, has_homepage, has_install_script,
                           risk_score, risk_level, is_hallucination, similar_to
                    FROM packages
                    WHERE experiment_id = ?
                    ORDER BY risk_score DESC
                """, (exp_id,)).fetchall()

                pkg_list = []
                for p in pkgs:
                    pd = dict(p)
                    # boolean 변환
                    for key in ("pypi_exists", "npm_exists", "has_repo_url",
                                "has_homepage", "has_install_script", "is_hallucination"):
                        pd[key] = bool(pd.get(key))
                    # JSON 필드 파싱
                    if pd.get("similar_to"):
                        try:
                            pd["similar_to"] = json.loads(pd["similar_to"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    pkg_list.append(pd)

                results.append({
                    "experiment_id": exp_id,
                    "question_id": exp_dict["question_id"],
                    "question_text": exp_dict["question_text"],
                    "domain": exp_dict["domain"],
                    "model_name": exp_dict["model_name"],
                    "run_number": exp_dict["run_number"],
                    "raw_response": exp_dict["raw_response"],
                    "tokens_used": exp_dict["tokens_used"],
                    "latency_ms": exp_dict["latency_ms"],
                    "error": exp_dict["error"],
                    "created_at": exp_dict["created_at"],
                    "packages": pkg_list,
                    "package_count": len(pkg_list),
                    "hallucination_count": sum(1 for p in pkg_list if p.get("is_hallucination")),
                })

            return results
