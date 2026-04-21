# AI 슬롭스쿼팅 탐지기

> **LLM 패키지 환각 기반 공급망 공격 탐지 도구**
> GitHub: https://github.com/yujin1103/Ai_Slopsquatting

---

## 1. 프로젝트 개요

### 문제 정의

**슬롭스쿼팅(Slopsquatting)** — LLM이 존재하지 않는 패키지명을 **환각(hallucinate)**하는 현상을 악용한 공급망 공격.

```
① AI가 가짜 패키지 추천 (환각)
② 공격자가 PyPI/npm에 그 이름으로 악성 패키지 선점
③ 개발자가 AI 추천을 믿고 pip install
④ 악성코드 실행
```

### 해결 방식

AI 추천 패키지를 **실시간으로** 검사하여 개발자가 설치하기 전에 경고.

| 경로 | 동작 시점 |
|---|---|
| **Chrome Extension** | AI 응답 생성 시점 (claude.ai / chatgpt.com / gemini.google.com) |
| **VSCode Extension** | 코드 편집 시점 (import 문) |
| **CLI** | 수동 파일 검사 |
| **n8n Workflow** | 자동화 리포트 |

### 차별점

| 기존 도구 | 본 프로젝트 |
|---|---|
| 설치 전 의존성 파일 검사 | **AI 응답 시점 즉시 검사** |
| 메타데이터만 확인 | **소스코드 아카이브까지 분석** |
| CLI/CI/CD 중심 | **브라우저 실시간 감지** |

---

## 2. 시스템 구조

```
사용자 환경 (Chrome Ext / VSCode Ext / CLI)
            │
            ▼
FastAPI 서버 (Docker :8001)
 ├─ Layer 1: 메타데이터 (PyPI/npm 등록, 편집거리, 합성 패턴)
 └─ Layer 2: 소스코드 분석 (악성 패턴 9종, 아카이브 스트리밍)
            │
            ▼
    CRITICAL / HIGH / MEDIUM / LOW
```

### 판정 공식

```
미등록 패키지: Layer 1 점수 (최소 80점 CRITICAL)
등록된 패키지: (소스 점수 × 신뢰도 계수) + 의심 가산
```

신뢰도 계수로 오래된/활성 패키지의 오탐을 억제.
예: pandas (5953일, v114, 인기) → `소스 40 × 0.2 × 0.7 × 0.5 = 2점 (LOW)`

---

## 3. 설치 및 실행

### 요구사항

- Docker Desktop (필수)
- Chrome (Chrome Extension용)
- VSCode + Node.js 18+ (VSCode Extension용, 선택)

### Step 1: API 서버

```bash
cd Ai_Slopsquatting
docker compose up -d --build
curl http://localhost:8001/health    # 동작 확인
```

### Step 2: Chrome Extension

1. Chrome → `chrome://extensions`
2. **개발자 모드** ON
3. **"압축해제된 확장 프로그램을 로드합니다"** → `slop-detector-extension` 폴더 선택

### Step 3: VSCode Extension

```bash
cd vscode-slop-detector
code --install-extension slopsquatting-detector-0.1.0.vsix
```

---

## 4. 테스트 시나리오

### Chrome Extension

Claude.ai / ChatGPT / Gemini에서:
- "flask로 게시판 만들어줘" → 초록 LOW 패널
- "fastapi-redis-rbac-bouncer 써봐" → 빨간 CRITICAL 경고

### VSCode Extension

`demo_test.py`:
```python
import flask                       # LOW
import flsk                        # CRITICAL → flask 제안
import tensorfloww                 # CRITICAL → tensorflow 제안
import fastapi_redis_rbac_bouncer  # CRITICAL (미등록)
```

- 빨간 밑줄 + `💡 혹시 'flask'를 찾으셨나요?` CodeLens
- 클릭 시 자동 교체 / `Ctrl+.`로 Quick Fix

### API 직접 호출

```bash
curl -X POST http://localhost:8001/analyze \
  -H "Content-Type: application/json" \
  -d '{"packages":["flask","fastapi-redis-rbac-bouncer"]}'
```

---

## 5. 리뷰 포인트

### 핵심 코드 모듈

| 모듈 | 위치 | 검토 포인트 |
|---|---|---|
| L1 분석 | `secure_capstone/api/main.py` | 점수 가중치, 합성 패턴 탐지 |
| L2 소스 분석 | `secure_capstone/source_analyzer.py` | 악성 패턴 9종, 아카이브 스트리밍 |
| Chrome Extension | `slop-detector-extension/content/` | 사이트별 DOM 감지 |
| VSCode Extension | `vscode-slop-detector/src/` | Diagnostic, CodeLens, QuickFix |

### 주요 의사결정

- **AI 사이트 실시간 감지 우선** — IDE 연동은 AI 응답 이후의 방어선이라 Chrome Extension을 먼저 구현
- **Layer 1/2 분리** — 등록된 악성 패키지도 탐지하기 위해 소스 아카이브 분석 추가
- **곱셈 신뢰도 할인** — 가감산 방식은 소스 점수가 높을 때 오탐 억제 부족 → 곱셈으로 비율 할인

---

## 6. 연구 실험 결과

GPT-4o 100회 호출 (20 질문 × 5회, python_ml 도메인):

| 항목 | 수치 |
|---|---|
| 추출 패키지 | 358개 |
| 할루시네이션 | **19개 (5.3%)** |

> 틈새/신흥 분야(BERT distillation, continual learning 등)일수록 할루시네이션율이 높음. 범용 라이브러리(flask, numpy)는 0%.

---

## 7. 현재 한계

- Anthropic Claude / Gemini 실험 미완료 (API 키 이슈)
- Cargo(Rust) 에코시스템 미지원
- 배포 시 사용자도 Docker 필요 → 하이브리드 구조(L1 JS 포팅) 전환 검토 중

---

## 8. FAQ

**Q. Docker 서버가 꺼져있으면?**
Chrome Extension이 "오프라인" 표시. `docker compose up -d`로 실행.

**Q. API 호출 비용은?**
탐지 자체는 0원 (PyPI/npm 공개 API). 유료 API는 연구 실험에서만 사용.

**Q. Claude UI가 변경되면?**
토큰 밀도 기반 동적 셀렉터로 일부 변경에 자동 대응. 큰 구조 변경 시 업데이트 필요.

**Q. 소스 분석 속도?**
패키지당 1~3초. SHA-256 캐시(30분)로 반복 요청 즉시 반환.
