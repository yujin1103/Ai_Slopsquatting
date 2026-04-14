# AI 슬롭스쿼팅 탐지기 — 진행 상황 보고서

> Capstone Design 2026 PROJECT  
> SEC-RESEARCH-LAB  
> 보고일: 2026-04-14

---

## 1. 프로젝트 개요

### 제안서 목표
LLM(대규모 언어 모델)이 추천하는 패키지 중 실제로는 존재하지 않거나, 존재하지만 악의적인 패키지를 실시간으로 탐지하는 도구 개발.

### 핵심 위협 모델
```
LLM 환각(Hallucination) → 존재하지 않는 패키지명 반복 추천
    → 공격자가 해당 이름으로 악성 패키지를 레지스트리에 선점 등록
    → 개발자가 AI 추천을 믿고 설치
    → 악성코드 실행 (공급망 공격)
```

### 연구 배경 (제안서 기준)
- 슬롭스쿼팅 관련 논문 16편, 관련 데이터 576K+ 건 참조
- 실제 침해 사례: `react-codeshift` — 237개 리포지토리 영향
- LLM이 생성한 가짜 패키지명(`graphdatabase` 등)이 실제 공격에 활용 가능

---

## 2. 제안서 vs 현재 구현 비교

### 2.1 설계 목표 달성 현황

| 제안서 설계 목표 | 현재 상태 | 비고 |
|---|:---:|---|
| 실시간 존재 여부 검증 (PyPI/npm API) | **완료** | Layer 1 메타데이터 분석 |
| 위험도 기반 점수 산출 (0~100점) | **완료** | Layer 1 + Layer 2 통합 판정 |
| 모델별 환각률 비교 분석 | **부분 완료** | GPT-4o 100회 완료, Anthropic 키 이슈 |
| HTML 대시보드 리포트 | **완료** | n8n 워크플로우 + MD 리포트 |

### 2.2 제안서에 없었으나 추가 구현된 기능

| 추가 기능 | 설명 |
|---|---|
| **Layer 2 소스코드 분석** | PyPI/npm 아카이브를 메모리 스트리밍하여 악성 패턴 9종 탐지 (다운로드/설치 없음) |
| **Chrome Extension** | Claude, ChatGPT, Gemini 3개 사이트에서 실시간 인라인 패널 표시 |
| **자연어 패키지 감지** | `pip install` 없이도 백틱, import, 인기 패키지 사전 매칭으로 감지 |
| **SHA-256 캐시** | 동일 요청 30분 캐시로 API 호출 최소화 |

---

## 3. 시스템 아키텍처 (현재)

### 제안서 아키텍처
```
LLM 모델 질문 → 패키지 추출 → 위험도 점수 계산 → HTML Dashboard
```

### 현재 아키텍처
```
[사용자 경로 1: Chrome Extension]
AI 사이트 응답 → MutationObserver 감지 → 패키지명 추출
    → background.js (SHA-256 캐시) → FastAPI :8001
    → Layer 1 (메타데이터) + Layer 2 (소스 분석)
    → 인라인 결과 패널 (LOW/MEDIUM/HIGH/CRITICAL)

[사용자 경로 2: CLI]
소스 파일 → slop_check.py → FastAPI :8001 → 터미널 Rich 출력

[사용자 경로 3: n8n 자동화]
워크플로우 트리거 → Gemini API → 패키지 추출 → 분석 → HTML 리포트
```

### 기술 스택

| 계층 | 기술 |
|---|---|
| Chrome Extension | Manifest V3, content scripts (사이트별 분리) |
| API 서버 | FastAPI + uvicorn + httpx + rapidfuzz (Docker :8001) |
| 소스 분석 | 아카이브 메모리 스트리밍, 악성 패턴 9종, Shannon 엔트로피 |
| 코드 파서 | Python AST + Regex 하이브리드 (py/js/ts/json) |
| CLI | slop_check.py + Rich |
| 자동화 | n8n Workflow (:5679) + Gemini API |
| 연구 파이프라인 | OpenAI GPT-4o, 비동기 실험, SQLite, JSON/MD 리포트 |

---

## 4. 위험도 판정 체계

### 제안서 기준 (단일 계층)

| 시그널 | 점수 |
|---|:---:|
| PyPI/npm 미등록 | +55 |
| 7일 이내 신규 등록 | +25 |
| 유사 패키지 존재 | +20 |
| 합성 패턴 | +15 |
| 편집거리 (Levenshtein) | +5~20 |

### 현재 기준 (Layer 기반, 강화됨)

**Layer 1 — 메타데이터 분석 (모든 패키지)**

| 시그널 | 점수 | 변경 사항 |
|---|:---:|---|
| PyPI 미등록 | **+70** | 55 → 70 상향 |
| npm에도 미등록 | **+10** | 신규 추가 |
| 7일 이내 신규 등록 | +25 | 동일 |
| 30일 이내 등록 | +15 | 동일 |
| 합성 패턴 | +20 | 15 → 20 상향 |
| 편집거리 ≤2 | +20 | 동일 |
| 편집거리 ≤4 | +8 | 동일 |
| 버전 1개 | +10 | 동일 |
| npm에만 존재 (생태계 혼동) | +15 | 동일 |

**Layer 2 — 소스코드 분석 (등록된 패키지만)**

| 탐지 패턴 | 점수 | 설명 |
|---|:---:|---|
| install_hook | +20 | setup.py cmdclass 오버라이드 |
| exec_eval | +15 | exec(), eval(), compile() |
| base64_exec | +25 | base64 디코딩 + exec 조합 |
| credential_theft | +25 | os.environ + requests.post |
| shell_execution | +15 | subprocess, os.system |
| obfuscated_import | +10 | `__import__('os')` |
| network_access | +10 | socket, urllib 직접 사용 |
| npm_install_script | +25 | postinstall 악용 |
| high_entropy_string | +10 | Shannon 엔트로피 > 4.5 |

**신뢰도 할인 계수 (오탐 억제)**

등록된 패키지라도 내부적으로 `eval()`, `subprocess` 등을 정상 목적으로 사용하는 경우 오탐이 발생합니다. 이를 막기 위해 소스 점수에 신뢰도 할인 계수를 **곱하여** 최종 점수를 조정합니다. 조건은 중첩 적용됩니다.

| 조건 | 할인 계수 | 예시 |
|---|:---:|---|
| 등록 2000일 초과 (5년+) | × 0.2 | pandas (5953일) |
| 등록 1000일 초과 (3년+) | × 0.3 | 안정적 활성 패키지 |
| 등록 365일 초과 (1년+) | × 0.5 | 1년 이상 유지 패키지 |
| 버전 50개 이상 | × 0.7 | 지속 업데이트 패키지 |
| 버전 10개 이상 | × 0.9 | 소규모 활성 패키지 |
| 인기 패키지 목록 포함 | × 0.5 | numpy, pandas, flask 등 321개 |

**의심 가산 (독립 시그널, 할인과 별도 덧셈)**

| 조건 | 가산 |
|---|:---:|
| 등록 30일 이내 (신규) | +10 |
| 유사 이름 존재 (편집거리 ≤2) | +10 |
| 버전 1개 이하 | +5 |

```
최종 점수 = (소스 점수 × trust_factor) + suspicion
```

예시:
```
pandas:  소스 40점 × 0.2(5953일) × 0.7(v114) × 0.5(인기) = 2점 → LOW
sklearn: 소스 10점 × 0.2(3925일) × 0.9(v10) + 10(유사) = 11점 → LOW
flask:   소스 0점 × 0.2(5841일) × 0.7(v64) × 0.5(인기) = 0점 → LOW
신규 악성: 소스 60점 × 1.0(5일) + 10(신규) + 5(v1) = 75점 → HIGH
```

**최종 판정**

| 등급 | 점수 범위 | 의미 |
|---|:---:|---|
| CRITICAL | 80~100 | 즉시 위험 — 미등록이거나 악성 패턴 다수 |
| HIGH | 60~79 | 높은 위험 — 의심 시그널 복합 |
| MEDIUM | 30~59 | 주의 필요 — 일부 시그널 존재 |
| LOW | 0~29 | 안전 — 정상 등록 패키지 |

**핵심 변경: 미등록 패키지 = 최소 CRITICAL**
- PyPI + npm 양쪽 미등록 → 80점 (CRITICAL)
- 소스코드 분석이 불가능하므로 더 높은 경각심 부여

---

## 5. 연구 실험 결과

### 제안서 계획
- 5개 질문, Gemini 2.5 Flash / Claude / Cohere 3개 모델 비교
- 119 Total Samples, Risk Score 80/100 CRITICAL

### 현재 결과 (GPT-4o)

| 항목 | 수치 |
|---|---|
| 모델 | GPT-4o |
| 질문 수 | 20개 (python_ml 도메인) |
| 반복 횟수 | 5회 / 질문 |
| 총 LLM 호출 | 100회 |
| 추출 패키지 | 358개 |
| 할루시네이션 | 19개 |
| **할루시네이션율** | **5.3%** |

### 할루시네이션 상위 질문

| 질문 | 할루시네이션 | 비율 |
|---|:---:|:---:|
| Knowledge distillation (BERT) | 5개 | 36% |
| Continual learning (catastrophic forgetting) | 4개 | 22% |
| Multi-armed bandit algorithms | 3개 | 18% |
| Gradient-based NAS | 3개 | 17% |

> **발견:** 틈새/신흥 분야일수록 할루시네이션율이 높음. 범용 라이브러리(flask, numpy 등) 질문에서는 0%.

### 파서 정확도 개선

| 항목 | 개선 전 | 개선 후 |
|---|:---:|:---:|
| 추출 패키지 | 387개 | 358개 |
| 할루시네이션 | 43개 (11.1%) | **19개 (5.3%)** |
| 오검출 | 24개 | 0개 |

오검출 유형 (제거됨):
- Placeholder: `your_app_file_name`, `dummy_input`
- 서브모듈 경로: `torch.quantization`, `torch.onnx.export`
- 클래스명: `MLFlowLogger`, `ImageDataGenerator`

---

## 6. Chrome Extension 개발 현황

### 제안서 계획
제안서 Future Roadmap에 "개발 환경(IDE) 실시간 연동"으로 언급.

### 현재 구현

| 항목 | 상태 |
|---|---|
| manifest.json (v3) | **완료** |
| Claude.ai 감지 | **완료** — 코드블록 + 텍스트 + 아티팩트 |
| ChatGPT 감지 | **완료** — 코드블록 + 텍스트 + span 패턴 |
| Gemini 감지 | **완료** — 코드블록 + 자연어 NLP 감지 |
| 인라인 결과 패널 | **완료** — L1/L2 상세 토글, 위험도 색상 |
| background.js 캐시 | **완료** — SHA-256, 30분 TTL |
| popup UI | **완료** — 서버 상태 + 누적 통계 |

### 감지 방식 (3단계)

| 단계 | 방식 | 신뢰도 |
|:---:|---|:---:|
| 1 | `pip install` / `npm install` 패턴 | 높음 |
| 2 | 백틱 인라인 코드 + import 패턴 | 중간 |
| 3 | 130+ 인기 패키지 사전 매칭 | 중간 |

### 버그 수정 이력

| 버그 | 원인 | 수정 |
|---|---|---|
| 아티팩트 패널 중복 생성 | 스트리밍 중 코드 변화로 키 매번 변경 | debounce + 카드 즉시 잠금 |
| 아티팩트 코드 미감지 | `min-w-0 max-w-full` 클래스 하드코딩 | 토큰 밀도 기반 동적 탐색 |
| iframe postMessage 미구현 | 로그만 출력, 패널 미생성 | 패널 생성 + 3단계 삽입 전략 |
| 동일 패키지 반복 시 UI 미표시 | Set 기반 중복 방지 | DOM 패널 존재 여부로 대체 |

---

## 7. 역할 분담 대비 진행 현황

### 제안서 역할 분담

| 팀원 | 역할 | 현재 진행 |
|---|---|---|
| 이동건 | AI 입력 처리 및 패키지 추출 | **완료** — LLM 클라이언트 + 파서 개선 |
| 강한승 | 위험도 분석 엔진 | **완료** — Layer 1 + Layer 2 엔진 |
| 김지혜 | CLI 개발 및 리포트 생성 | **완료** — CLI + MD/JSON 리포트 |
| 정은 | 시스템 통합 및 환경 구축 | **완료** — Docker + n8n + Extension |

---

## 8. Future Roadmap 대비 현황

| 제안서 로드맵 | 현재 상태 | 비고 |
|---|:---:|---|
| 환각 패턴 DB 구축 (데이터베이스) | **진행 중** | GPT-4o 100회 결과 SQLite 저장, JSON/MD 리포트 생성 |
| safe-npm 도구 통합 | **부분 완료** | npm 레지스트리 API 연동, source_analyzer.py에서 postinstall 검사 |
| 개발 환경(IDE) 실시간 연동 | **대체 구현** | IDE 대신 Chrome Extension으로 AI 사이트 직접 연동 (더 넓은 범위) |

---

## 9. 프로젝트 디렉토리 구조

```
Ai_Slopsquatting/
├── slop-detector-extension/           # Chrome Extension (신규)
│   ├── manifest.json
│   ├── background.js                  # SHA-256 캐시 + API 통신
│   ├── content/
│   │   ├── common.js                  # 공통 유틸 + NLP 패키지 감지
│   │   ├── claude.js                  # claude.ai 전용
│   │   ├── chatgpt.js                 # chatgpt.com 전용
│   │   ├── gemini.js                  # gemini.google.com 전용
│   │   └── artifact.js               # a.claude.ai iframe
│   ├── popup.html / popup.js
│   └── test/                          # 자동화 테스트
├── secure_capstone/
│   ├── source_analyzer.py             # L2 소스코드 분석 (신규)
│   ├── api/
│   │   ├── main.py                    # FastAPI 핵심 분석 로직
│   │   ├── import_parser.py           # AST + Regex 파서
│   │   └── Dockerfile
│   ├── research/
│   │   ├── llm_client.py              # GPT-4o / Claude / Gemini
│   │   ├── pipeline.py                # 실험 파이프라인
│   │   ├── validator.py               # 패키지 존재 여부 검증
│   │   ├── analyzer.py                # JSON/MD 리포트 생성
│   │   └── database.py                # SQLite 결과 저장
│   └── reports/
│       ├── architecture_diagram.html  # 시스템 구조도
│       ├── gpt4o_research_report.md   # GPT-4o 실험 결과
│       └── CHANGELOG.md               # 변동사항 이력
├── github_typo_hunter.py              # GitHub 오타 탐사 도구
├── slop_manual_v2.json                # n8n 워크플로우
├── docker-compose.yml
└── CLAUDE.md                          # 프로젝트 문서
```

---

## 10. 사용된 API 및 비용

| API | 용도 | 비용 |
|---|---|---|
| PyPI JSON API | L1 메타데이터 조회 | 무료 |
| npm Registry API | L1 메타데이터 조회 | 무료 |
| PyPI/npm CDN | L2 소스 아카이브 스트리밍 | 무료 |
| OpenAI GPT-4o | 연구 실험 (환각률 측정) | 유료 (API 크레딧) |
| GitHub Search API | 오타 패키지 탐사 | 무료 (토큰 필요) |

> 탐지 파이프라인 자체는 **비용 0원**. 유료 API는 연구 실험에서만 사용.

---

## 11. 향후 과제

1. **Anthropic Claude 실험 추가** — API 키 갱신 후 100회 실험 재실행
2. **Gemini 실험 추가** — Google API 키 설정 후 동일 파이프라인으로 실행
3. **환각 패턴 DB 확장** — 도메인별 (웹, 데이터, 보안 등) 질문 추가
4. **Extension 안정화** — Claude UI 변경에 대응하는 폴백 셀렉터 강화
5. **GitHub Typo Hunter 연동** — 오타 패키지의 선점 여부를 자동 모니터링
