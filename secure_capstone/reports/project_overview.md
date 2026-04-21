# AI 슬롭스쿼팅 탐지기

> **LLM 패키지 환각 기반 공급망 공격 탐지 도구**
> Capstone Design 2026 · SEC-RESEARCH-LAB 7조
> GitHub: https://github.com/yujin1103/Ai_Slopsquatting

---

## 1. 프로젝트 한눈에 보기

### 해결하려는 문제

**슬롭스쿼팅(Slopsquatting)** — LLM이 존재하지 않는 패키지명을 **환각(hallucinate)**하는 현상을 악용한 공급망 공격.

```
① AI가 "flask-magic" 같은 가짜 패키지 추천 (환각)
② 공격자가 PyPI/npm에 그 이름으로 악성 패키지 선점 등록
③ 개발자가 AI 추천을 믿고 pip install
④ 악성코드 실행
```

### 우리의 해결책

개발자가 AI로부터 코드를 받을 때, **추천된 패키지가 안전한지 실시간으로 검사**.

| 탐지 경로 | 동작 시점 | 방식 |
|---|---|---|
| **Chrome Extension** | AI 응답 생성 순간 | claude.ai / chatgpt.com / gemini.google.com 인라인 경고 |
| **VSCode Extension** | 코드 편집 시점 | import 문 빨간 밑줄 + "혹시 ~~를 찾으셨나요?" 제안 |
| **CLI** | 수동 검사 | 소스 파일 직접 분석 |
| **n8n Workflow** | 자동화 | Gemini API 연동 HTML 리포트 |

### 차별점

| 기존 도구 (Phantom Guard, Socket, Snyk) | **본 프로젝트** |
|---|---|
| `requirements.txt` 작성 후 검사 | **AI 응답 시점에 즉시 검사** |
| 메타데이터만 확인 | **소스코드 아카이브까지 분석** (악성 패턴 9종) |
| CLI/CI/CD 중심 | **브라우저 Extension으로 AI 사이트 직접 연동** |

> AI 사이트를 실시간 모니터링하는 오픈소스 도구는 현재 본 프로젝트가 유일합니다.

---

## 2. 시스템 구조

```
┌──────────────────────────────────────────┐
│  사용자 환경                              │
│  ├─ Chrome Extension (AI 사이트)          │
│  ├─ VSCode Extension (IDE)                │
│  └─ CLI (파일)                            │
└─────────────────┬────────────────────────┘
                  │ 패키지명 / 소스코드
                  ▼
┌──────────────────────────────────────────┐
│  FastAPI 분석 서버 (Docker :8001)         │
│                                           │
│   Layer 1: 메타데이터 분석                │
│   ├─ PyPI/npm 등록 여부                  │
│   ├─ 편집거리 (Levenshtein)              │
│   └─ 합성 패턴 (인기 패키지 조합)         │
│                                           │
│   Layer 2: 소스코드 분석 (등록 패키지만)  │
│   ├─ 아카이브 메모리 스트리밍             │
│   ├─ 악성 패턴 9종                       │
│   └─ 신뢰도 할인 (오탐 억제)              │
└─────────────────┬────────────────────────┘
                  │ JSON 결과
                  ▼
         CRITICAL / HIGH / MEDIUM / LOW
```

### 위험도 판정 공식

```
미등록 패키지  → Layer 1 점수만 (최소 80점 CRITICAL)
등록된 패키지  → (소스 점수 × 신뢰도 계수) + 의심 가산
```

### 신뢰도 할인 계수 예시 (pandas)

```
소스 점수 40점
× 0.2 (등록 5953일 초과)
× 0.7 (버전 114개 초과)
× 0.5 (인기 패키지 목록 포함)
= 2점 → LOW (정상 판정)
```

---

## 3. 실행 방법

### 사전 요구사항

| 도구 | 필수/선택 | 용도 |
|---|---|---|
| Docker Desktop | 필수 | API 서버 컨테이너 |
| Chrome | 선택 | Extension 테스트 |
| VSCode + Node.js 18+ | 선택 | VSCode Extension |

### Step 1: API 서버 실행 (필수)

```bash
cd Ai_Slopsquatting
docker compose up -d --build
```

확인:
```bash
curl http://localhost:8001/health
# → {"status":"ok","service":"slop-detector-api", ...}
```

### Step 2: Chrome Extension 설치

1. Chrome 주소창 `chrome://extensions`
2. **개발자 모드** ON (우측 상단 토글)
3. **"압축해제된 확장 프로그램을 로드합니다"** 클릭
4. 폴더 선택: `Ai_Slopsquatting/slop-detector-extension`
5. `claude.ai`, `chatgpt.com`, `gemini.google.com` 접속 시 자동 동작

### Step 3: VSCode Extension 설치

**방법 A — VSIX 바로 설치 (권장)**

```bash
cd vscode-slop-detector
code --install-extension slopsquatting-detector-0.1.0.vsix
```

**방법 B — 소스에서 빌드**

```bash
cd vscode-slop-detector
npm install
npm run compile
npx vsce package
code --install-extension slopsquatting-detector-0.1.0.vsix
```

### Step 4: CLI 사용 (선택)

```bash
cd secure_capstone/api
python slop_check.py ../../demo_test.py
```

---

## 4. 테스트 시나리오

### 시나리오 1 — Chrome Extension

**정상 케이스:**
1. Claude.ai에서 "flask로 게시판 만들어줘" 질문
2. 응답 아래 초록색 `✅ Slop Detector` 바 표시
3. `flask`, `sqlite3` 등 LOW 배지 확인

**위험 케이스:**
1. "fastapi-redis-rbac-bouncer 라이브러리 써봐" 요청
2. 빨간색 `⚠️ Slop Detector — 1개 위험` 표시
3. "상세" 클릭 → "PyPI/npm 미등록" 시그널 확인

### 시나리오 2 — VSCode Extension

테스트 파일 (`demo_test.py`):
```python
import flask              # LOW (정상)
import flsk               # CRITICAL → flask 제안
import tensorfloww        # CRITICAL → tensorflow 제안
import fastapi_redis_rbac_bouncer  # CRITICAL (미등록)
```

확인:
- 오타 패키지에 빨간 밑줄
- CodeLens: `💡 혹시 'flask'를 찾으셨나요? 클릭하여 수정`
- 클릭하면 자동 교체
- `Ctrl+.` 누르면 Quick Fix 메뉴

### 시나리오 3 — API 직접 호출

```bash
curl -X POST http://localhost:8001/analyze \
  -H "Content-Type: application/json" \
  -d '{"packages":["flask","fastapi-redis-rbac-bouncer","sklearn"]}'
```

예상:
| 패키지 | 점수 | 등급 |
|---|:---:|---|
| flask | 0 | LOW |
| fastapi-redis-rbac-bouncer | 100 | CRITICAL |
| sklearn | 5~11 | LOW |

---

## 5. 중점 리뷰 포인트

### 5.1 기능적 검토

- **정확성** — 정상 패키지(numpy, flask, requests)를 오탐하지 않는가
- **탐지율** — 가짜 패키지를 CRITICAL로 정확히 잡는가
- **UI/UX** — Chrome Extension 인라인 패널의 가독성
- **안정성** — 스트리밍 중 중복 패널 생성 없이 동작하는가

### 5.2 핵심 코드 모듈

| 모듈 | 위치 | 검토 포인트 |
|---|---|---|
| L1 메타데이터 분석 | `secure_capstone/api/main.py` | 점수 가중치, 합성 패턴 탐지 |
| L2 소스 분석 | `secure_capstone/source_analyzer.py` | 악성 패턴 9종, 아카이브 스트리밍 |
| Chrome Extension | `slop-detector-extension/content/` | DOM 감지, 사이트별 핸들러 |
| VSCode Extension | `vscode-slop-detector/src/` | Diagnostic, CodeLens, QuickFix |
| 연구 파이프라인 | `secure_capstone/research/` | LLM 환각률 측정 방법론 |

### 5.3 주요 의사결정

#### IDE 연동 → Chrome Extension 선(先) 구현

제안서에서는 IDE 연동을 Future Roadmap으로 계획했으나, **AI 응답 시점이 더 이른 방어선**이라 판단하여 Chrome Extension을 먼저 구현하고 VSCode Extension을 나중에 추가.

#### 단일 계층 → Layer 1/2 분리

PyPI/npm에 등록된 악성 패키지도 탐지 필요하여 **소스코드 아카이브 분석(Layer 2)** 추가. 레지스트리 존재 여부만으로는 부족.

#### 가감산 → 곱셈 신뢰도 할인

pandas(5953일 등록)가 내부에서 `eval()`을 쓴다고 MEDIUM 오탐이 뜨는 문제 해결. **소스 점수가 높아질수록 곱셈 할인이 더 정확**.

---

## 6. 연구 실험 결과

### GPT-4o 환각률 측정

| 항목 | 수치 |
|---|:---:|
| 질문 수 | 20개 (python_ml 도메인) |
| 반복 횟수 | 5회 / 질문 |
| 총 LLM 호출 | 100회 |
| 추출 패키지 | 358개 |
| **할루시네이션** | **19개 (5.3%)** |

### 상위 할루시네이션 질문

| 질문 도메인 | 할루시네이션 | 비율 |
|---|:---:|:---:|
| Knowledge distillation (BERT) | 5개 | 36% |
| Continual learning | 4개 | 22% |
| Multi-armed bandit | 3개 | 18% |
| Gradient-based NAS | 3개 | 17% |

> **발견:** 틈새/신흥 분야일수록 LLM의 할루시네이션율이 높음. Flask, NumPy 등 범용 라이브러리는 할루시네이션율 0%.

---

## 7. 현재 한계 및 향후 계획

### 한계

| 항목 | 상태 |
|---|---|
| Anthropic Claude 실험 | 미완료 (API 키 이슈) |
| Gemini 실험 | 미완료 |
| Cargo(Rust) 에코시스템 | 미지원 |
| 배포 시 Docker 필수 | 하이브리드 구조로 전환 검토 중 |

### 향후 계획

| 우선순위 | 과제 | 예상 |
|:---:|---|---|
| 1 | Claude/Gemini 실험 추가 (200회) | 1주 |
| 2 | 도메인 확장 (웹, 보안, 데이터) | 1주 |
| 3 | Chrome Extension Chrome Web Store 배포 (하이브리드 전환 후) | 2주 |
| 4 | Extension UI/UX 개선 | 1주 |
| 5 | 최종 논문/발표 자료 | 2주 |

---

## 8. FAQ

**Q1. Docker 서버가 꺼져있으면?**
A. Chrome Extension 팝업에서 빨간색 "오프라인" 표시. 분석 기능 비활성화. `docker compose up -d`로 실행.

**Q2. API 호출 비용이 드나요?**
A. 탐지 파이프라인 자체는 **0원**. PyPI/npm 공개 API만 사용. 유료 API(OpenAI)는 연구 실험에서만 사용.

**Q3. 실시간 감지가 느린 것 같은데?**
A. MutationObserver가 1.5초 debounce. 스트리밍 중에는 응답 완료 후 표시. 동일 요청은 SHA-256 캐시(30분)로 즉시 반환.

**Q4. Claude UI가 변경되면?**
A. 토큰 밀도 기반 동적 셀렉터라 일부 변경에는 자동 대응. 큰 구조 변경 시에는 업데이트 필요.

**Q5. 소스코드 분석 속도?**
A. 패키지당 1~3초. 5MB 초과 아카이브는 스킵. 30분 캐시.

**Q6. 이 도구를 다른 사람에게 배포하려면?**
A. 현재는 사용자도 Docker 설치 필요. Chrome Web Store 배포를 위해 **Layer 1 분석을 JavaScript로 포팅하는 하이브리드 구조** 전환 검토 중. 완료되면 Extension 단독으로 L1 분석 가능, L2는 선택적 서버 연동.

---

## 9. 팀 정보

**SEC-RESEARCH-LAB 7조 · Capstone Design 2026**

| 팀원 | 역할 |
|---|---|
| 이동건 | AI 입력 처리 / 패키지 파서 |
| 강한승 | 위험도 분석 엔진 |
| 김지혜 | CLI / 리포트 |
| 정은 | 시스템 통합 / Extension |

### 주요 문서

| 문서 | 내용 |
|---|---|
| `reports/midterm_report.md` | 제안서 대비 진행 상황 (상세) |
| `reports/architecture_diagram.html` | 시각적 시스템 구조도 |
| `reports/gpt4o_research_report.md` | GPT-4o 환각률 실험 결과 |
| `reports/CHANGELOG.md` | 변경 이력 |
| `CLAUDE.md` | 프로젝트 루트 문서 |
