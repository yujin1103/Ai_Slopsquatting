# V2 탐지 엔진 재설계 문서

> 현직자 피드백 (2026-04-24) + 학술 논문 기반  
> V1은 `v1-legacy` 브랜치에 보존

---

## 1. V1의 한계 (폐기 사유)

| 문제 | 영향 |
|---|---|
| 정규식 9종 기반 패턴 매칭 | 난독화/변형된 공격 탐지 불가 |
| 개별 시그널 점수 합산 | 코드 문맥(시퀀스) 무시 |
| 신뢰도 할인 (기간/인기도) | 신규 정상 패키지 = 오탐, 신규 악성 패키지 = 미탐 |
| 전체 파일 스캔 시도 | 느리고 비효율적 |

**현직자 지적:** "단순 키워드, 평판, 오래된 거 기준으로는 정확한 판단 어려움. **행위 기반** 탐지가 필요."

---

## 2. V2 설계 원칙

### 2.1 3가지 핵심 원칙

1. **부분 분석, 높은 신뢰** — 전체 파일이 아닌 **공격 루트(entry point)** 만 정밀 분석
2. **시퀀스 기반 탐지** — 개별 API 호출이 아닌 **행위 체인** (`read → encode → send` 등)
3. **AI 이중 검증** — 정적 분석 + LLM 보안 리뷰로 설득력 강화

### 2.2 참고한 학술 근거

| 논문 | 핵심 기여 |
|---|---|
| **Cerebro** ([arXiv:2309.02637](https://arxiv.org/abs/2309.02637), ACM TOSEM 2025) | 16 features + Behavior Sequence + BERT, PyPI 683개 / npm 799개 신규 악성 탐지 |
| **DONAPI** ([USENIX Security 2024](https://www.usenix.org/system/files/sec24fall-prepub-171-huang-cheng.pdf)) | 132 API 모니터링, 12 behavior types, 40 subtypes |
| **Empirical Study PyPI** ([lcwj3.github.io](https://lcwj3.github.io/img_cs/pdf/An%20Empirical%20Study%20of%20Malicious%20Code%20In%20PyPI%20Ecosystem.pdf)) | 실제 악성 PyPI 패키지의 공격 파일 분포 실증 |

### 2.3 핵심 인사이트 (연구 결과)

> **4가지 Attack Dimension이 조합되어 실제 공격을 구성한다.**
> 
> 1. **Information Reading** (파일/환경변수/자격증명 읽기)
> 2. **Data Transmission** (네트워크 송신)
> 3. **Encoding/Obfuscation** (base64, eval)
> 4. **Payload Execution** (exec, subprocess)
> 
> 단독 호출이 아니라 **체인 시퀀스**로 분석해야 의미 있음.  
> 예: `os.environ → base64 → requests.post` (credential theft)

---

## 3. V2 아키텍처

```
Input: 패키지명
  ↓
[Stage 0] Layer 1 존재 확인 (참고용, 단독 판정 X)
  ├─ PyPI/npm 미등록 → "할루시네이션 확인하세요" 안내만
  └─ 등록됨 → Stage 1 진행
  ↓
[Stage 1] Entry Point 추출 (부분 분석의 근거)
  ├─ PyPI:   setup.py, pyproject.toml, __init__.py, __main__.py
  └─ npm:    package.json scripts, postinstall, main, bin
  ↓
[Stage 2] Behavior Sequence 추출
  ├─ Tree-sitter / AST로 파싱
  ├─ 4 Dimension API 호출 탐지
  │   ├─ Read:     os.environ, fs.readFile, subprocess.check_output
  │   ├─ Encode:   base64, compile, atob, btoa
  │   ├─ Execute:  exec, eval, subprocess, spawn
  │   └─ Network:  requests, urllib, http, socket, fetch
  └─ 호출 순서 → 시퀀스 벡터
  ↓
[Stage 3] MITRE ATT&CK / ATLAS 매칭
  ├─ TTP DB (사전 구축, 임베딩 벡터)
  ├─ 시퀀스 → Sentence-Transformer로 임베딩
  ├─ pgvector/Qdrant로 유사도 검색
  └─ Top-K 매칭 기술 (예: T1486, T1059, T1552)
  ↓
[Stage 4] LLM 이중 검증
  ├─ Claude Sonnet API 호출 (서버 크레딧)
  ├─ 우리 프롬프트 (Cerebro + MITRE 매칭 결과 첨부)
  └─ LLM이 시퀀스 설명 + 위험도 판단
  ↓
[Stage 5] 최종 리포트
  ├─ 매칭된 MITRE 기술 리스트
  ├─ 위험 행위 시퀀스 (전/후 관계 그래프)
  ├─ 코드 발췌 (근거)
  └─ LLM 코멘트
  ↓
[Stage 6] 서버 캐시 (PostgreSQL + Redis)
  └─ 다음 사용자는 즉시 반환 (분석이 오래 걸려도 1회만)
```

---

## 4. 부분 분석 전략 — 핵심 연구 주제

### 4.1 왜 Entry Point만 보는가

실증 연구에 따르면 악성 코드의 **대부분이 자동 실행되는 위치**에 있다:

| 위치 | 실행 시점 | 실제 악성 패키지 비율 |
|---|---|---|
| `setup.py` (PyPI) | pip install 중 | **50% 이상** |
| `__init__.py` | import 시 | ~20% |
| `package.json > scripts.postinstall` (npm) | npm install 중 | **60% 이상** |
| `index.js` / `main` 엔트리 | require/import 시 | ~20% |
| `bin/*` | 직접 실행 | ~5% |

> **"설치만 해도 실행되는 코드"가 공격의 핵심.** 나머지 수백~수천 파일은 정상 라이브러리 코드일 확률이 높음.

### 4.2 Tiered Analysis (단계별 심화)

```
Tier 1: ALWAYS (고정 분석 대상)
  ├─ setup.py, pyproject.toml
  ├─ package.json (scripts 섹션)
  ├─ __init__.py (루트)
  ├─ __main__.py
  └─ index.js, main 필드 파일

Tier 2: TRIGGERED (Tier 1에서 의심 시)
  ├─ Tier 1이 import하는 모듈 1-hop
  ├─ bin/, scripts/, postinstall.js
  └─ 인코딩된 문자열 (base64, hex) 포함 파일

Tier 3: AI DEEP DIVE (Tier 1+2에서 고위험 시)
  ├─ 전체 .py/.js 중 suspicious file만 (크기 < 50KB 우선)
  └─ LLM에게 컨텍스트 포함 전체 리뷰 요청
```

### 4.3 부분 분석의 타당성 (설득 논리)

- "**공격자는 빠른 실행을 원한다**" → 자동 실행 위치에 코드 삽입
- "**공격자가 수동 import 유도 + 사용 경로까지 구축**하기는 어려움" → Entry Point 중심 공격이 압도적
- **Cerebro 논문도 동일 결론**: 전체 파일이 아닌 suspicious file + AST 부분 분석으로 683+799개 신규 탐지 달성

> 리뷰어 설득 시:  
> **"우리는 전체를 보지 않지만, 실제 공격의 80% 이상이 집중되는 핵심 경로를 AI와 TTP DB로 다각 검증합니다."**

---

## 5. 구현 로드맵

### Phase 1 — 연구 & 데이터 수집 (1~2주)

- [ ] MITRE ATT&CK / ATLAS JSON 다운로드 + 전처리
- [ ] OWASP Top 10 for LLM 매핑 테이블 구축
- [ ] 악성 패키지 샘플 수집
  - [ ] Snyk vulnerability DB
  - [ ] GitHub Advisory Database (GHSA)
  - [ ] PyPI/npm Safety DB
  - [ ] 목표: Ground Truth **50~100개** (양성 50 + 음성 50)
- [ ] Entry Point 통계 실측 (수집한 악성 샘플 기준)

### Phase 2 — Behavior Sequence 엔진 (2주)

- [ ] `detector/ast_parser.py` — tree-sitter 기반 Python/JS AST
- [ ] `detector/api_catalog.py` — 4 Dimension API 카탈로그 (Cerebro 16 features 참고)
- [ ] `detector/sequence_extractor.py` — 호출 순서 추출
- [ ] `detector/entry_point.py` — Tier 1 파일 식별

### Phase 3 — 벡터 DB + MITRE 매칭 (2주)

- [ ] MITRE TTP 설명 → Sentence-Transformer 임베딩
- [ ] pgvector or Qdrant 설치 + 인덱스 구축
- [ ] 시퀀스 → 벡터 → Top-K 검색 API
- [ ] 매칭 결과 스코어링

### Phase 4 — LLM 이중 검증 (1주)

- [ ] Claude API 서버 통합 (크레딧 서버 부담)
- [ ] 프롬프트 설계 (`/security-review` 스타일)
  - 우리 추출 시퀀스 + MITRE 매칭 결과 첨부
- [ ] Rate limit + 캐시

### Phase 5 — 캐시 계층 (3일)

- [ ] PostgreSQL: 패키지명 + 버전 + 결과 JSON
- [ ] Redis: hot cache (최근 1000건)
- [ ] 버전 변경 감지 → 자동 재분석

### Phase 6 — 벤치마크 (1주)

- [ ] Ground Truth 50+50으로 Precision/Recall 측정
- [ ] 최근 유명 공급망 공격 사례 재현
  - axios 사건, colors.js, event-stream, eslint-scope-3.7.2 등
- [ ] Claude 기본 `/security-review`와 비교
- [ ] **목표: Claude 기본 리뷰에서 놓친 1건 이상을 우리 엔진이 추가 탐지**

### Phase 7 — 기존 Extension/CLI 재연결 (3일)

- [ ] FastAPI 엔드포인트 V2 버전 추가
- [ ] Chrome/VSCode Extension에서 V2 호출
- [ ] 결과 표시 UI 업데이트 (MITRE 기술 + 시퀀스 시각화)

---

## 6. V1 대비 V2의 차이

| 항목 | V1 | V2 |
|---|---|---|
| 분석 대상 | 패키지 전체 + setup.py | **Tier 1 Entry Point만** |
| 탐지 방식 | 정규식 9종 | **AST 시퀀스 + MITRE 벡터 검색 + LLM** |
| 속도 | 1~3초 | 10초 ~ 5분 (서버 캐시로 2회차는 즉시) |
| 점수 로직 | 가감산 + 신뢰도 할인 계수 | MITRE 매칭 강도 + LLM confidence |
| 데이터 소스 | 자체 패턴 | MITRE ATT&CK / ATLAS / OWASP LLM Top 10 |
| AI 활용 | 없음 (Layer 1/2 수동) | Claude API 이중 검증 |
| 캐시 | Extension client-side 30분 | **서버 영구 캐시** (버전 변경 전까지) |

---

## 7. 우선 실행 사항

- [x] `v1-legacy` 브랜치 생성 완료
- [ ] **연구 데이터 수집 스크립트** 작성 (악성 패키지 Ground Truth)
- [ ] MITRE JSON 다운로드 자동화
- [ ] Tier 1 파일 실증 통계 (악성 샘플 분석)

다음 작업: **연구 데이터 수집 단계**부터 착수.
