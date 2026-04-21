# AI 슬롭스쿼팅 탐지기 — 리뷰어 가이드

> **검토자를 위한 프로젝트 소개 및 실행 가이드**  
> 2026-04-14 / SEC-RESEARCH-LAB

---

## 1. 프로젝트 한눈에 보기

### 1.1 해결하려는 문제

**슬롭스쿼팅(Slopsquatting)** — LLM(Claude, ChatGPT, Gemini 등)이 코드 추천 시 실제로 존재하지 않는 패키지명을 환각(hallucinate)하는 현상을 악용한 **공급망 공격**입니다.

```
① AI가 "flask-magic" 같은 가짜 패키지 추천
② 공격자가 PyPI에 그 이름으로 악성 패키지 선점 등록
③ 개발자가 AI 추천을 믿고 pip install
④ 악성코드 실행
```

### 1.2 프로젝트가 하는 일

개발자가 AI로부터 코드를 받을 때, **추천된 패키지가 안전한지 실시간으로 검사**합니다.

| 탐지 경로 | 동작 방식 |
|---|---|
| **Chrome Extension** | Claude/ChatGPT/Gemini 응답에서 패키지명 감지 → 응답 아래에 인라인 경고 표시 |
| **VSCode Extension** | import 문을 자동 감지 → 빨간 밑줄 + "혹시 ~~를 찾으셨나요?" 제안 |
| **CLI** | 소스 파일을 직접 검사 → 터미널에 위험도 출력 |
| **n8n Workflow** | Gemini API 자동화 → HTML 리포트 생성 |

### 1.3 차별점

| 기존 도구 (Phantom Guard, Socket, Snyk) | 본 프로젝트 |
|---|---|
| `requirements.txt` 작성 후 검사 | **AI 응답 시점에 즉시 검사** |
| 메타데이터만 확인 | **소스코드 아카이브까지 분석** (9종 악성 패턴) |
| CLI/CI/CD 중심 | **브라우저 Extension으로 AI 사이트 직접 연동** |

AI 사이트를 실시간 모니터링하는 오픈소스 도구는 현재 이 프로젝트가 유일합니다.

---

## 2. 시스템 구조

```
┌─────────────────────────────────────────┐
│  사용자 환경 (Browser / VSCode / CLI)     │
└─────────────────┬───────────────────────┘
                  │ 패키지명 / 소스코드
                  ▼
┌─────────────────────────────────────────┐
│  FastAPI 분석 서버 (Docker :8001)        │
│                                          │
│   Layer 1: 메타데이터 분석               │
│   ├─ PyPI/npm 등록 여부                 │
│   ├─ 편집거리 (Levenshtein)             │
│   └─ 합성 패턴 (인기 패키지 조합 탐지)    │
│                                          │
│   Layer 2: 소스코드 분석 (등록 패키지만)  │
│   ├─ 아카이브 메모리 스트리밍            │
│   ├─ 악성 패턴 9종 (base64+exec 등)      │
│   └─ 신뢰도 할인 (오래된 패키지 오탐 억제) │
└─────────────────┬───────────────────────┘
                  │ JSON 결과
                  ▼
         CRITICAL / HIGH / MEDIUM / LOW
```

---

## 3. 실행 방법

### 3.1 사전 요구사항

| 도구 | 버전 | 용도 |
|---|---|---|
| Docker Desktop | 최신 | API 서버 컨테이너 |
| Chrome | 최신 | Extension 테스트 |
| Node.js (선택) | 18+ | VSCode Extension 빌드 |

### 3.2 Step 1: API 서버 실행 (필수)

모든 탐지 경로가 이 서버를 사용합니다.

```bash
# 프로젝트 루트에서
cd Ai_Slopsquatting
docker compose up -d --build
```

**확인:**
```bash
curl http://localhost:8001/health
# → {"status":"ok","service":"slop-detector-api","version":"2.0.0", ...}
```

### 3.3 Step 2: Chrome Extension 설치

1. Chrome 주소창에 `chrome://extensions` 입력
2. 우측 상단 **개발자 모드** 토글 ON
3. **"압축해제된 확장 프로그램을 로드합니다"** 클릭
4. 폴더 선택:
   ```
   Ai_Slopsquatting/slop-detector-extension
   ```
5. 설치 완료 → `claude.ai`, `chatgpt.com`, `gemini.google.com` 접속 시 자동 동작

### 3.4 Step 3: VSCode Extension 실행 (선택)

```bash
cd vscode-slop-detector
npm install
npm run compile
```

VSCode에서 `vscode-slop-detector/` 폴더 열고 **F5**로 Extension Host 실행.

### 3.5 Step 4: CLI 사용 (선택)

```bash
cd secure_capstone/api
python slop_check.py ../research/test_samples/example.py
```

---

## 4. 테스트 시나리오

### 4.1 Chrome Extension 테스트

**정상 케이스 (안전 표시):**
1. Claude.ai에서 "flask로 웹서버 만들어줘" 질문
2. 응답 아래에 초록색 `Slop Detector` 바가 표시됨
3. `flask` 배지에 마우스 올리면 "LOW" 상세 정보

**위험 케이스 (경고 표시):**
1. "fastapi-redis-rbac-bouncer 써봐" 같이 가짜 패키지 언급
2. 빨간색 CRITICAL 경고 표시됨
3. "상세" 클릭 → "PyPI/npm 미등록", "합성 패턴 의심" 시그널 확인

### 4.2 VSCode Extension 테스트

테스트 파일 생성:
```python
# test.py
import flask              # 정상 (LOW)
import flsk               # 오타 (MEDIUM + 힌트)
import fastapi_redis_rbac_bouncer  # 존재하지 않음 (CRITICAL)
```

**확인 사항:**
- `flsk`에 빨간 밑줄
- 위에 `💡 혹시 'flask'를 찾으셨나요? 클릭하여 수정` 표시
- 클릭 → 자동으로 `flask`로 교체

### 4.3 API 직접 호출

```bash
curl -X POST http://localhost:8001/analyze \
  -H "Content-Type: application/json" \
  -d '{"packages":["flask","fastapi-redis-rbac-bouncer","sklearn"]}'
```

예상 결과:
| 패키지 | 점수 | 등급 |
|---|:---:|---|
| `flask` | 0 | LOW |
| `fastapi-redis-rbac-bouncer` | 100 | CRITICAL |
| `sklearn` | 5~11 | LOW (sklearn은 정상, scikit-learn과 유사하여 표시만) |

---

## 5. 중점 리뷰 포인트

### 5.1 기능적 검토

- **정확성**: 정상 패키지(numpy, flask, requests)를 오탐하지 않는지
- **효율성**: 가짜 패키지(존재하지 않는 이름)를 CRITICAL로 잡는지
- **UI/UX**: Chrome Extension 인라인 패널이 가독성 있는지
- **응답성**: 스트리밍 중 중복 패널 생성 없이 안정적인지

### 5.2 코드 검토

| 모듈 | 위치 | 검토 포인트 |
|---|---|---|
| L1 메타데이터 분석 | `secure_capstone/api/main.py` | 점수 가중치, 합성 패턴 탐지 |
| L2 소스 분석 | `secure_capstone/source_analyzer.py` | 악성 패턴 정규식, 아카이브 스트리밍 |
| Chrome Extension | `slop-detector-extension/content/` | DOM 감지 로직, postMessage 처리 |
| VSCode Extension | `vscode-slop-detector/src/` | Diagnostic, CodeLens, QuickFix |
| 연구 파이프라인 | `secure_capstone/research/` | LLM 환각률 측정 방법론 |

### 5.3 문서 검토

| 문서 | 내용 |
|---|---|
| `CLAUDE.md` | 프로젝트 구조 + 위협 모델 |
| `reports/midterm_report.md` | 제안서 대비 진행 상황 |
| `reports/CHANGELOG.md` | 변경 이력 |
| `reports/architecture_diagram.html` | 시스템 구조도 (브라우저로 열기) |
| `reports/gpt4o_research_report.md` | GPT-4o 환각률 실험 결과 |

---

## 6. 주요 의사결정 및 트레이드오프

### 6.1 IDE 연동 → Chrome Extension 전환

**제안서:** IDE 연동을 Future Roadmap으로 계획  
**현재:** Chrome Extension 선(先) 구현, VSCode Extension 후(後) 추가

**이유:** AI 사이트에서 코드를 복사하기 전 시점에 경고하는 것이 더 이른 방어선. IDE는 이미 복사한 후의 방어선.

### 6.2 단일 계층 → Layer 1/2 분리

**제안서:** 메타데이터 기반 단일 점수  
**현재:** L1(메타데이터) + L2(소스 분석) 2계층

**이유:** PyPI/npm에 등록된 악성 패키지도 탐지 필요. 레지스트리 존재 여부만으로는 부족.

### 6.3 가감산 → 곱셈 신뢰도 할인

**초기:** `final = source + meta_adjust` (±20점 가감)  
**현재:** `final = source × trust_factor + suspicion` (비율 감산)

**이유:** pandas(5953일 등록)가 내부에서 `eval()`을 쓴다고 MEDIUM 오탐이 뜨면 안 됨. 소스 점수가 높아질수록 곱셈이 더 정확.

---

## 7. 현재 제약사항

| 항목 | 현재 상태 | 계획 |
|---|---|---|
| Anthropic Claude 환각 실험 | 미완료 (API 키 이슈) | 키 갱신 후 100회 실행 |
| Gemini 환각 실험 | 미완료 | Google API 키 설정 후 실행 |
| Chrome Extension UI 커스터마이징 | 고정 색상/크기 | 설정 페이지 추가 예정 |
| 다국어 지원 | 한국어만 | 영어 추가 예정 |
| Cargo(Rust) 에코시스템 | 미지원 | 향후 추가 검토 |

---

## 8. 연락처 및 참고

### 프로젝트 리포지토리
```
https://github.com/yujin1103/Ai_Slopsquatting
```

### 문서 우선순위 (리뷰 시간별)

| 시간 | 추천 경로 |
|---|---|
| **10분** | 본 가이드 + `architecture_diagram.html` 확인 |
| **30분** | 위 + `midterm_report.md` 전체 + Chrome Extension 설치 테스트 |
| **1시간+** | 위 + `source_analyzer.py` 코드 리뷰 + VSCode Extension 테스트 |

### 팀 정보
SEC-RESEARCH-LAB 캡스톤 디자인 2026 / 7조

---

## 9. 자주 묻는 질문

**Q1. Docker 서버가 안 떠 있으면?**  
Chrome Extension 팝업에서 빨간색 "오프라인" 표시. 분석 기능 비활성화. `docker compose up -d`로 실행.

**Q2. API 호출 비용이 드나요?**  
아니요. PyPI/npm 공개 API만 사용합니다. 연구 모듈의 LLM 실험에서만 OpenAI 크레딧 사용.

**Q3. 실시간 감지가 느린 것 같은데?**  
MutationObserver가 1.5초 debounce됩니다. 스트리밍 중에는 응답 완료 후 나타납니다. SHA-256 캐시(30분)로 반복 요청은 즉시 반환.

**Q4. Claude UI가 변경되면?**  
DOM 셀렉터 일부가 동적 탐색 방식(토큰 밀도 기반)이라 일부 변경에는 자동 대응. 큰 구조 변경 시에는 업데이트 필요.

**Q5. 소스코드 분석은 얼마나 오래 걸리나요?**  
패키지당 1~3초. 5MB 초과 아카이브는 스킵. 30분 캐시로 반복 분석 방지.
