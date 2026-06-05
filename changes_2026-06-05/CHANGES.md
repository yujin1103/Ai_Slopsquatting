# 2026-06-05 변경사항 요약

## 1. 엔진 변경 (pkgsentinel · 이미 푸시됨)
- **verdict_rules.py — 휴리스틱 단독 미승격 (B-to-SUSPICIOUS)**: 휴리스틱 룰
  (indicator-47 / sequence / anomaly / string-analysis)이 LLM·신뢰 인텔 확인 없이
  단독으로 SUSPICIOUS 이상으로 승격하지 못하게 제한. numpy 등 정상 패키지의
  대량 휴리스틱 오탐 제거. (commit 2c19bdf)
- **threat_db known_popular 적재**: top-PyPI 5,000개 → 편집거리 기반 typosquat/
  slopsquat 탐지 활성화 (panddas→pandas 등). 인기도 보정 아님(참조 리스트).
- **README**: 피드 적재 단계 + claude 모드(ANTHROPIC_API_KEY) setup 보강.

## 2. 발표자료 슬라이드 편집 (pkgsentinel_deck_appended.pptx)
- **슬라이드 6~12 (L0~L6 부록)**: 각 레이어 표 아래 **numpy 실측 패널** 추가.
  L0 깨끗 → L2~L4 휴리스틱 138 비-benign 신호 폭증 → L5 Claude 전부 benign →
  L6 최종 CLEAN. (production claude로 numpy=CLEAN 검증)
- **슬라이드 17/18 (실험 1)**: npm 비교 → **PyPI 출하 엔진 비교**로 교체.
  인기도 보정 OFF, production decide_verdict 기준.
- **슬라이드 19 (실험 2)**: 원본 유지 (아래 4번 회귀 발견으로 검토 필요).

## 3. 실험 1 — PyPI 혼합셋 (n=139, 출하 엔진, 인기도 보정 OFF)
악성 80(DataDog) + 정상 59(PyPI 인기). production run_pipeline + decide_verdict.

| 도구 | Recall | Precision | F1 | 정상 FP |
|---|---|---|---|---|
| **pkgsentinel (출하엔진·claude)** | **0.848** | **1.000** | **0.918** | **0/59** |
| OSV-Scanner | 0.763 | 0.984 | 0.859 | 1/59 |
| Bandit | 0.475 | 0.463 | 0.469 | 44/56 (79%) |
| Semgrep | 0.212 | 0.298 | 0.247 | 40/59 (68%) |

핵심: **인기도 보정 없이 정상 59개 전부 CLEAN (FP 0)** — 이전 슬라이드 18의
"FP 2/59"는 eval 전용 인기도 화이트리스트로 나온 값이었음(출하 엔진엔 없는 보정).

## 4. 실험 2 — 다중 사건 zero-day (출하 엔진, claude) ⚠️ 중요 발견
| 캠페인 | n | 탐지 | Recall | 이전 슬라이드 |
|---|---|---|---|---|
| Shai-Hulud (2025-09 npm worm) | 162 | 162 | **1.000** | 100% ✓ |
| TrapDoor (2026-05 지갑탈취) | 46 | 37 | **0.804** | 78% ✓ |
| **Mini Shai-Hulud (2026-05 TeamPCP)** | 40 | 1 | **0.025** ⚠️ | 100% → **급락** |

**Mini Shai-Hulud 회귀 원인**: 이 캠페인은 대형 정상 패키지(@mistralai/*,
@squawk/* 등; evidence 4,700~5,200개)에 소형 악성 페이로드를 주입한
**compromised-library형**. B-to-SUSPICIOUS(휴리스틱 단독 미승격) 때문에 거대
패키지 속 소형 페이로드의 휴리스틱 신호가 승격되지 못하고, claude per-file 검증도
대량의 정상 파일에 희석되어 CLEAN으로 빠짐.

**→ trade-off**: numpy 등 정상 FP 제거(실험1 FP 0)와, compromised-library형
악성 탐지 급락(Mini 100%→2.5%)을 맞바꿈. 슬라이드 19에 반영하기 전 설계 재검토
필요(예: 거대 패키지의 소형 payload 농도 신호를 별도 승격 경로로 살리기).

## 5. 측정 방법 (재현)
- `scripts/eval_prod.py`: 캐시 아카이브를 run_pipeline에 주입(check/extract_all
  monkeypatch)하여 정상·악성을 동일 production 경로로 측정.
- `scripts/run_exp2.py`: 캠페인별(Shai/Mini/TrapDoor) recall 측정.
- 비교도구: Bandit(native), Semgrep(docker), OSV(api.osv.dev) — 기존 스크립트.
