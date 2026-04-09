# AI Slopsquatting 탐지 프로젝트

## 프로젝트 개요
LLM이 추천하는 패키지 중 PyPI/npm에 등록되어 있지만 악의적인 패키지(슬롭스쿼팅)를 탐지하는 도구.

**핵심 위협 모델:** LLM 할루시네이션으로 존재하지 않는 패키지명이 반복 추천됨 → 공격자가 해당 이름으로 악성 패키지를 레지스트리에 등록 → 개발자가 AI 추천을 믿고 설치 → 악성코드 실행

## 현재 구조

```
secure_capstone/
├── source_analyzer.py          # 소스코드 정적 분석 (공용 모듈)
├── api/                        # 메인 탐지 API (FastAPI)
│   ├── main.py                 # 핵심 분석 로직 + 엔드포인트
│   ├── import_parser.py        # 하이브리드 파서 (AST + Regex)
│   ├── slop_check.py           # CLI 도구
│   ├── data/
│   │   └── popular_python_packages.txt
│   ├── Dockerfile
│   └── requirements.txt
├── research/                   # LLM 환각률 측정 모듈 (추후 분리 예정)
│   ├── llm_client.py           # GPT-4o / Claude / Gemini 클라이언트
│   ├── pipeline.py             # 실험 파이프라인 + JSON 리포트 자동 생성
│   ├── analyzer.py             # HTML/JSON 리포트 생성
│   ├── validator.py            # 패키지 검증 (메타데이터 + 소스 분석)
│   ├── database.py             # SQLite (실험 결과 + 소스 분석 결과 저장)
│   ├── questions.py            # 500+ 질문 데이터셋
│   └── config.py
├── __else/
│   └── safe-npm/               # npm 전용 안전 검사 모듈
├── reports/                    # 생성된 HTML/JSON 리포트 + 구조도
└── docker-compose.yml
```

## 확정된 설계 방향

### 핵심 목적
PyPI/npm에 **등록되어 있지만 악의적인** 패키지를 탐지하는 것에 집중.
- 레지스트리(PyPI/npm)는 악성 패키지를 전부 차단하지 못함 (업로드 시 코드 리뷰 없음)
- 공격자 등록 → 레지스트리 삭제까지의 시간 창(time window)이 공격 기회
- 우리 도구는 이 시간 창을 메움

### 분석 파이프라인: Layer 기반

```
패키지명 입력
    │
    ▼
Layer 1: 존재 확인 (게이트)
    │   PyPI/npm API 메타데이터 조회
    │   - 등록 여부, 등록일, 버전 수
    │   - repo URL, homepage 유무
    │   - 유사 패키지명 (편집거리, 합성 패턴)
    │
    ├─ 미등록 → 즉시 CRITICAL 경고 (소스 분석 불가)
    │
    └─ 등록됨 → Layer 2로 진행
              │
              ▼
         Layer 2: 악의성 분석 (본질)
              │   아카이브를 메모리 스트리밍 (다운로드/설치 없음)
              │   setup.py, __init__.py, index.js 등 핵심 파일만 추출
              │
              │   탐지 패턴:
              │   - install_hook (+20): setup.py cmdclass 오버라이드
              │   - exec_eval (+15): exec(), eval(), compile()
              │   - base64_exec (+25): base64 디코딩 → exec 조합
              │   - credential_theft (+25): os.environ + requests.post
              │   - shell_execution (+15): subprocess, curl/wget
              │   - obfuscated_import (+10): __import__('os')
              │   - network_access (+10): socket, urllib 직접 사용
              │   - npm_install_script (+25): postinstall 악용
              │   - high_entropy_string (+10): 난독화 문자열
              │
              │   메타데이터 보조 가중:
              │   - 30일 이내 신규 등록 → +10
              │   - 유사 이름 존재 → +10
              │   - 버전 1개 → +5
              │
              ▼
         최종 판정
              CRITICAL (≥80) / HIGH (≥60) / MEDIUM (≥30) / LOW (<30)
```

### 사용 방식 (현재): CLI + Docker API
- `slop_check.py` CLI로 소스 파일 직접 검사
- FastAPI 서버 (Docker :8001) 가 분석 수행
- n8n 워크플로우 자동화 (:5679)

### 사용 방식 (예정): Chrome Extension
- AI 사이트(claude.ai, chatgpt.com, gemini.google.com)의 응답을 실시간 파싱
- MutationObserver로 DOM 변화 감지 → 코드 블록 추출
- 기존 `import_parser.py` 로직을 재활용해 패키지명 추출
- 결과는 인라인 뱃지/경고로 표시
- API 서버는 로컬 Docker (타겟: 개발자)

## TODO

### 1. Chrome Extension 개발
- manifest.json 구성
- content script: MutationObserver로 AI 응답 감지
- 코드 블록 파싱 → 로컬 FastAPI 서버 호출
- 결과 UI (인라인 뱃지, 경고 패널)
- 지원 사이트: claude.ai, chatgpt.com, gemini.google.com

### 2. 위험도 스코어링 추가 시그널 (선택적 고도화)
- PyPI Stats API 주간 다운로드 수 (낮으면 의심)
- description / author 필드 비어있음
- wheel 없이 sdist만 존재
- 의존성 0개 or 비정상적으로 많음
- Homoglyph 공격 탐지 (`0`↔`O`, `l`↔`I`↔`1`)
- GitHub repo star 수 (project_urls 활용)

## 분리 예정
`research/` 모듈 (LLM 환각률 측정)은 별도 프로젝트로 분리 예정. 현재는 건드리지 않음.
