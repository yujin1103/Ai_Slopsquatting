"""
슬롭스쿼팅 연구 파이프라인 메인 실행 파일

사용법:
  # 전체 실행 (500 질문 × 활성화된 모델 × 5회 반복)
  python pipeline.py run

  # 테스트 실행 (처음 10개 질문만)
  python pipeline.py run --limit 10

  # 특정 모델만
  python pipeline.py run --models gpt-4o claude-3-5-sonnet

  # 현재 진행 상황 확인
  python pipeline.py status

  # HTML 리포트 생성
  python pipeline.py report

  # JSON 리포트 생성 (질문+답변 전체 포함)
  python pipeline.py json-report
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import List, Optional

# 현재 디렉토리를 sys.path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from config import config
from database import Database
from llm_client import query_llm, LLMResponse
from validator import validate_packages_batch
from questions import QUESTIONS
from analyzer import generate_report, generate_json_report, print_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
# 핵심 파이프라인 로직
# ─────────────────────────────────────────────────────

def _save_experiment_json(
    question: dict,
    model_name: str,
    run_number: int,
    llm_resp: LLMResponse,
    pkg_infos: list,
    json_dir: str,
) -> None:
    """개별 실험 결과를 JSON 파일로 저장"""
    record = {
        "question_id": question["id"],
        "question_text": question["text"],
        "domain": question["domain"],
        "model_name": model_name,
        "run_number": run_number,
        "raw_response": llm_resp.raw_text,
        "extracted_packages": llm_resp.packages,
        "tokens_used": llm_resp.tokens_used,
        "latency_ms": llm_resp.latency_ms,
        "error": llm_resp.error,
        "timestamp": datetime.now().isoformat(),
        "packages": [
            {
                "name": p.name,
                "ecosystem": p.ecosystem,
                "pypi_exists": p.pypi_exists,
                "npm_exists": p.npm_exists,
                "pypi_upload_date": p.pypi_upload_date,
                "npm_publish_date": p.npm_publish_date,
                "days_since_published": p.days_since_published,
                "version_count": p.version_count,
                "has_repo_url": p.has_repo_url,
                "has_homepage": p.has_homepage,
                "has_install_script": p.has_install_script,
                "risk_score": p.risk_score,
                "risk_level": p.risk_level,
                "is_hallucination": p.is_hallucination,
                "similar_to": p.similar_to,
            }
            for p in pkg_infos
        ],
    }

    filename = f"q{question['id']}_{model_name}_run{run_number}.json"
    filepath = os.path.join(json_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


async def process_one(
    question: dict,
    model_name: str,
    run_number: int,
    db: Database,
    semaphore: asyncio.Semaphore,
    json_dir: str,
) -> int:
    """
    단일 (질문, 모델, 실행 번호) 조합 처리
    1. LLM 질의
    2. 패키지명 추출
    3. PyPI/npm 검증
    4. DB 저장
    5. 개별 JSON 파일 저장
    반환값: 저장된 패키지 수
    """
    # 이미 처리된 항목 스킵 (재실행 안전성)
    if db.is_already_done(question["id"], model_name, run_number):
        return 0

    async with semaphore:
        # 1. LLM 질의
        llm_resp: LLMResponse = await query_llm(
            question_id=question["id"],
            question_text=question["text"],
            run_number=run_number,
            model_name=model_name,
            config=config,
        )

        # 요청 간 딜레이 (속도 제한 대응)
        await asyncio.sleep(config.request_delay_seconds)

        # 2. DB에 experiment 저장
        exp_id = db.save_experiment(
            question_id=question["id"],
            question_text=question["text"],
            domain=question["domain"],
            model_name=model_name,
            run_number=run_number,
            raw_response=llm_resp.raw_text,
            tokens_used=llm_resp.tokens_used,
            latency_ms=llm_resp.latency_ms,
            error=llm_resp.error,
        )

        if not exp_id or not llm_resp.packages:
            # 패키지가 없어도 Q&A JSON은 저장
            _save_experiment_json(question, model_name, run_number, llm_resp, [], json_dir)
            return 0

        # 3. 패키지 검증
        pkg_infos = await validate_packages_batch(
            names=llm_resp.packages,
            pypi_base_url=config.pypi_base_url,
            npm_base_url=config.npm_base_url,
            concurrency=config.validation_concurrency,
            timeout=config.api_timeout_seconds,
        )

        # 4. DB 저장
        saved = db.save_packages(
            experiment_id=exp_id,
            question_id=question["id"],
            domain=question["domain"],
            model_name=model_name,
            packages=pkg_infos,
        )

        # 5. 개별 JSON 파일 저장
        _save_experiment_json(question, model_name, run_number, llm_resp, pkg_infos, json_dir)

        return saved


async def run_pipeline(
    questions: List[dict],
    models: List[str],
    runs_per_question: int,
    db: Database,
) -> None:
    """전체 파이프라인 실행"""

    # JSON 개별 결과 저장 디렉토리 생성
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_dir = os.path.join(config.report_dir, f"json_qa_{timestamp}")
    os.makedirs(json_dir, exist_ok=True)
    logger.info(f"개별 Q&A JSON 저장 경로: {json_dir}")

    # 처리할 전체 태스크 목록 생성
    tasks = []
    for q in questions:
        for model in models:
            for run in range(1, runs_per_question + 1):
                if not db.is_already_done(q["id"], model, run):
                    tasks.append((q, model, run))

    total = len(tasks)
    if total == 0:
        logger.info("모든 항목이 이미 처리되었습니다.")
        return

    logger.info(f"처리할 태스크: {total:,}개 "
                f"({len(questions)}개 질문 × {len(models)}개 모델 × {runs_per_question}회)")

    semaphore = asyncio.Semaphore(config.llm_concurrency)
    completed = 0
    total_packages = 0
    start_time = time.monotonic()

    # 배치 단위로 처리 (진행 상황 주기적 출력)
    batch_size = 10
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        batch_tasks = [
            process_one(q, model, run, db, semaphore, json_dir)
            for q, model, run in batch
        ]
        results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, int):
                total_packages += r
            elif isinstance(r, Exception):
                logger.error(f"태스크 오류: {r}")

        completed += len(batch)
        elapsed = time.monotonic() - start_time
        rate = completed / elapsed if elapsed > 0 else 0
        eta = (total - completed) / rate if rate > 0 else 0

        logger.info(
            f"진행: {completed:,}/{total:,} ({100*completed/total:.1f}%) | "
            f"패키지: {total_packages:,} | "
            f"속도: {rate:.1f}/s | "
            f"ETA: {eta/60:.1f}분"
        )

    elapsed_total = time.monotonic() - start_time
    logger.info(
        f"\n완료! 총 소요시간: {elapsed_total/60:.1f}분 | "
        f"처리된 태스크: {completed:,} | 저장된 패키지: {total_packages:,}"
    )

    # 전체 요약 JSON 리포트 자동 생성
    summary_path = os.path.join(config.report_dir, f"research_qa_report_{timestamp}.json")
    generate_json_report(db, summary_path)
    logger.info(f"전체 JSON 리포트 생성 완료: {summary_path}")


# ─────────────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────────────

def cmd_run(limit: Optional[int] = None, models: Optional[List[str]] = None) -> None:
    """파이프라인 실행"""
    try:
        config.validate()
    except ValueError as e:
        print(f"\n오류: {e}")
        sys.exit(1)

    config.ensure_dirs()
    db = Database(config.db_path)

    questions = QUESTIONS[:limit] if limit else QUESTIONS
    active_models = models if models else config.enabled_models()

    print(f"\n=== 슬롭스쿼팅 연구 파이프라인 시작 ===")
    print(f"  질문 수:      {len(questions):,}개")
    print(f"  활성 모델:    {', '.join(active_models)}")
    print(f"  반복 횟수:    {config.runs_per_question}회")
    print(f"  DB 경로:      {config.db_path}")
    print(f"  예상 호출:    {len(questions) * len(active_models) * config.runs_per_question:,}회\n")

    asyncio.run(run_pipeline(questions, active_models, config.runs_per_question, db))

    print("\n=== 최종 통계 ===")
    print_summary(db)


def cmd_status() -> None:
    """현재 진행 상황 출력"""
    if not os.path.exists(config.db_path):
        print("아직 실행된 적 없습니다. 먼저 'python pipeline.py run'을 실행하세요.")
        return
    db = Database(config.db_path)
    print_summary(db)


def cmd_report() -> None:
    """HTML 리포트 생성"""
    if not os.path.exists(config.db_path):
        print("데이터베이스가 없습니다. 먼저 'python pipeline.py run'을 실행하세요.")
        return

    config.ensure_dirs()
    db = Database(config.db_path)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    output = os.path.join(config.report_dir, f"research_report_{timestamp}.html")
    path = generate_report(db, output)
    print(f"리포트 생성 완료: {path}")


def cmd_json_report() -> None:
    """질문-답변 전체 데이터를 JSON 리포트로 생성"""
    if not os.path.exists(config.db_path):
        print("데이터베이스가 없습니다. 먼저 'python pipeline.py run'을 실행하세요.")
        return

    config.ensure_dirs()
    db = Database(config.db_path)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    output = os.path.join(config.report_dir, f"research_qa_report_{timestamp}.json")
    path = generate_json_report(db, output)
    print(f"JSON 리포트 생성 완료: {path}")


def print_help() -> None:
    print(__doc__)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    command = args[0]

    if command == "run":
        limit = None
        models = None
        i = 1
        while i < len(args):
            if args[i] == "--limit" and i + 1 < len(args):
                limit = int(args[i + 1]); i += 2
            elif args[i] == "--models" and i + 1 < len(args):
                models = []
                i += 1
                while i < len(args) and not args[i].startswith("--"):
                    models.append(args[i]); i += 1
            else:
                i += 1
        cmd_run(limit=limit, models=models)

    elif command == "status":
        cmd_status()

    elif command == "report":
        cmd_report()

    elif command == "json-report":
        cmd_json_report()

    else:
        print(f"알 수 없는 명령어: {command}")
        print_help()
        sys.exit(1)
