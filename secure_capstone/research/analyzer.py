"""
통계 분석 및 HTML 리포트 생성
수집된 데이터를 기반으로 연구 결과 수치화
"""

import json
import os
from datetime import datetime
from typing import Dict

from database import Database
from questions import DOMAIN_NAMES


def generate_report(db: Database, output_path: str) -> str:
    """분석 결과를 HTML 리포트로 생성"""
    progress   = db.get_progress()
    halluc     = db.get_hallucination_stats()
    risk_dist  = db.get_risk_distribution()
    top_halluc = db.get_top_hallucinated_packages(30)
    now        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_pkg  = progress["total_packages"]
    total_hall = progress["hallucinations"]
    hall_rate  = progress["hallucination_rate"]

    # ── 모델별 테이블 ─────────────────────────────────
    model_rows = ""
    for m in halluc["by_model"]:
        rate = m.get("rate", 0)
        color = "#e74c3c" if rate > 20 else "#f39c12" if rate > 10 else "#27ae60"
        model_rows += f"""
        <tr>
          <td><code>{m['model_name']}</code></td>
          <td>{m['total']:,}</td>
          <td>{m['hallucinations']:,}</td>
          <td style="color:{color}; font-weight:bold">{rate}%</td>
        </tr>"""

    # ── 도메인별 테이블 ───────────────────────────────
    domain_rows = ""
    for d in halluc["by_domain"]:
        domain_name = DOMAIN_NAMES.get(d["domain"], d["domain"])
        rate = d.get("rate", 0)
        color = "#e74c3c" if rate > 20 else "#f39c12" if rate > 10 else "#27ae60"
        domain_rows += f"""
        <tr>
          <td>{domain_name}</td>
          <td>{d['total']:,}</td>
          <td>{d['hallucinations']:,}</td>
          <td style="color:{color}; font-weight:bold">{rate}%</td>
        </tr>"""

    # ── 고위험 반복 할루시네이션 ──────────────────────
    repeated_cards = ""
    for p in halluc["high_risk_repeated"]:
        repeated_cards += f"""
        <div class="pkg-card critical">
          <span class="pkg-name">{p['package_name']}</span>
          <span class="badge">{p['model_count']} 모델</span>
          <span class="badge secondary">{p['total_mentions']} 회 언급</span>
        </div>"""

    # ── 전체 상위 할루시네이션 패키지 ─────────────────
    top_pkg_rows = ""
    for i, p in enumerate(top_halluc, 1):
        domain_name = DOMAIN_NAMES.get(p["domain"], p["domain"])
        top_pkg_rows += f"""
        <tr>
          <td>{i}</td>
          <td><code>{p['package_name']}</code></td>
          <td>{domain_name}</td>
          <td>{p['mention_count']:,}</td>
          <td>{p['model_count']}</td>
          <td>{p['question_count']}</td>
        </tr>"""

    # ── 위험 레벨 분포 바 ─────────────────────────────
    risk_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    risk_colors = {"CRITICAL": "#e74c3c", "HIGH": "#e67e22",
                   "MEDIUM": "#f1c40f", "LOW": "#27ae60", "UNKNOWN": "#95a5a6"}
    risk_bars = ""
    for lvl in risk_levels:
        cnt = risk_dist.get(lvl, 0)
        pct = round(cnt / total_pkg * 100, 1) if total_pkg > 0 else 0
        color = risk_colors.get(lvl, "#95a5a6")
        risk_bars += f"""
        <div class="risk-row">
          <span class="risk-label" style="color:{color}">{lvl}</span>
          <div class="risk-bar-wrap">
            <div class="risk-bar" style="width:{pct}%; background:{color}"></div>
          </div>
          <span class="risk-count">{cnt:,} ({pct}%)</span>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>슬롭스쿼팅 연구 리포트 — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; padding: 24px; }}
  h1 {{ font-size: 1.8rem; color: #fff; margin-bottom: 4px; }}
  h2 {{ font-size: 1.2rem; color: #aaa; margin: 28px 0 12px; border-bottom: 1px solid #333; padding-bottom: 6px; }}
  .subtitle {{ color: #666; font-size: 0.85rem; margin-bottom: 24px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 24px; }}
  .stat-card {{ background: #1a1d27; border-radius: 10px; padding: 18px; text-align: center; border: 1px solid #2a2d3a; }}
  .stat-num {{ font-size: 2.2rem; font-weight: bold; color: #7c8cf8; }}
  .stat-label {{ font-size: 0.8rem; color: #888; margin-top: 4px; }}
  .stat-num.danger {{ color: #e74c3c; }}
  .stat-num.warn {{ color: #f39c12; }}
  table {{ width: 100%; border-collapse: collapse; background: #1a1d27; border-radius: 8px; overflow: hidden; }}
  th {{ background: #23263a; padding: 10px 14px; text-align: left; font-size: 0.8rem; color: #888; text-transform: uppercase; }}
  td {{ padding: 10px 14px; border-top: 1px solid #23263a; font-size: 0.88rem; }}
  tr:hover td {{ background: #20233a; }}
  code {{ background: #23263a; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; color: #7c8cf8; }}
  .pkg-card {{ display: inline-flex; align-items: center; gap: 8px; background: #1a1d27; border: 1px solid #e74c3c44; border-radius: 8px; padding: 8px 14px; margin: 4px; }}
  .pkg-card.critical {{ border-color: #e74c3c55; }}
  .pkg-name {{ font-family: monospace; color: #e74c3c; font-weight: bold; }}
  .badge {{ background: #e74c3c22; color: #e74c3c; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }}
  .badge.secondary {{ background: #7c8cf822; color: #7c8cf8; }}
  .risk-row {{ display: flex; align-items: center; gap: 12px; margin: 8px 0; }}
  .risk-label {{ width: 80px; font-weight: bold; font-size: 0.85rem; }}
  .risk-bar-wrap {{ flex: 1; background: #23263a; border-radius: 4px; height: 18px; overflow: hidden; }}
  .risk-bar {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
  .risk-count {{ width: 120px; text-align: right; font-size: 0.82rem; color: #888; }}
  .section {{ background: #1a1d27; border-radius: 10px; padding: 20px; margin-bottom: 20px; border: 1px solid #2a2d3a; }}
</style>
</head>
<body>

<h1>🔍 슬롭스쿼팅 공격 가능성 연구 리포트</h1>
<p class="subtitle">생성일: {now} &nbsp;|&nbsp; LLM 할루시네이션 기반 패키지 위험도 분석</p>

<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-num">{progress['total_experiments']:,}</div>
    <div class="stat-label">총 LLM 호출 수</div>
  </div>
  <div class="stat-card">
    <div class="stat-num">{total_pkg:,}</div>
    <div class="stat-label">추출된 패키지명</div>
  </div>
  <div class="stat-card">
    <div class="stat-num danger">{total_hall:,}</div>
    <div class="stat-label">할루시네이션 (미존재)</div>
  </div>
  <div class="stat-card">
    <div class="stat-num warn">{hall_rate}%</div>
    <div class="stat-label">전체 할루시네이션률</div>
  </div>
  <div class="stat-card">
    <div class="stat-num">{len(halluc['high_risk_repeated'])}</div>
    <div class="stat-label">고위험 반복 할루시네이션</div>
  </div>
</div>

<h2>모델별 할루시네이션 비율</h2>
<div class="section">
  <table>
    <thead><tr><th>모델</th><th>총 패키지</th><th>할루시네이션</th><th>비율</th></tr></thead>
    <tbody>{model_rows}</tbody>
  </table>
</div>

<h2>도메인별 할루시네이션 비율</h2>
<div class="section">
  <table>
    <thead><tr><th>도메인</th><th>총 패키지</th><th>할루시네이션</th><th>비율</th></tr></thead>
    <tbody>{domain_rows}</tbody>
  </table>
</div>

<h2>위험 레벨 분포</h2>
<div class="section">
  {risk_bars}
</div>

<h2>⚠️ 고위험: 여러 모델에서 반복 추천된 미존재 패키지</h2>
<div class="section">
  <p style="color:#888; font-size:0.85rem; margin-bottom:12px">
    아래 패키지는 2개 이상의 LLM 모델이 동시에 추천했지만 실제로 존재하지 않습니다.<br>
    공격자가 이 이름으로 패키지를 등록할 경우 즉시 슬롭스쿼팅 공격이 가능합니다.
  </p>
  {repeated_cards if repeated_cards else '<p style="color:#666">아직 데이터가 충분하지 않습니다.</p>'}
</div>

<h2>전체 할루시네이션 패키지 Top 30</h2>
<div class="section">
  <table>
    <thead>
      <tr>
        <th>#</th><th>패키지명</th><th>도메인</th>
        <th>언급 횟수</th><th>모델 수</th><th>질문 수</th>
      </tr>
    </thead>
    <tbody>{top_pkg_rows}</tbody>
  </table>
</div>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def generate_json_report(db: Database, output_path: str) -> str:
    """질문-답변 전체 데이터를 JSON 리포트로 생성.
    각 실험의 질문, LLM 원본 응답, 추출 패키지, 검증 결과를 모두 포함."""
    qa_data = db.get_full_qa_data()
    progress = db.get_progress()
    halluc = db.get_hallucination_stats()
    risk_dist = db.get_risk_distribution()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = {
        "meta": {
            "generated_at": now,
            "description": "슬롭스쿼팅 연구 - 질문/답변 전체 리포트",
        },
        "summary": {
            "total_experiments": progress["total_experiments"],
            "total_packages": progress["total_packages"],
            "hallucinations": progress["hallucinations"],
            "hallucination_rate": progress["hallucination_rate"],
            "model_counts": progress["model_counts"],
        },
        "stats": {
            "by_model": halluc["by_model"],
            "by_domain": halluc["by_domain"],
            "high_risk_repeated": halluc["high_risk_repeated"],
            "risk_distribution": risk_dist,
        },
        "experiments": qa_data,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return output_path


def print_summary(db: Database) -> None:
    """터미널에 요약 통계 출력 (rich 없이도 동작)"""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import print as rprint

        console = Console()
        progress = db.get_progress()
        halluc   = db.get_hallucination_stats()

        console.print("\n[bold cyan]═══ 슬롭스쿼팅 연구 현황 ═══[/bold cyan]\n")
        console.print(f"  총 LLM 호출:        [bold]{progress['total_experiments']:,}[/bold]")
        console.print(f"  추출된 패키지:       [bold]{progress['total_packages']:,}[/bold]")
        console.print(f"  할루시네이션:        [bold red]{progress['hallucinations']:,}[/bold red]")
        console.print(f"  할루시네이션률:      [bold yellow]{progress['hallucination_rate']}%[/bold yellow]\n")

        t = Table(title="모델별 통계")
        t.add_column("모델"); t.add_column("총 패키지"); t.add_column("할루시네이션"); t.add_column("비율")
        for m in halluc["by_model"]:
            rate = str(m.get("rate", 0)) + "%"
            color = "red" if m.get("rate", 0) > 20 else "yellow" if m.get("rate", 0) > 10 else "green"
            t.add_row(m["model_name"], str(m["total"]), str(m["hallucinations"]), f"[{color}]{rate}[/{color}]")
        console.print(t)

    except ImportError:
        # rich 없이 기본 출력
        progress = db.get_progress()
        print("\n=== 슬롭스쿼팅 연구 현황 ===")
        print(f"총 LLM 호출: {progress['total_experiments']:,}")
        print(f"추출된 패키지: {progress['total_packages']:,}")
        print(f"할루시네이션: {progress['hallucinations']:,} ({progress['hallucination_rate']}%)")
