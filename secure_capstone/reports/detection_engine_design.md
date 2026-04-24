# 탐지 엔진 설계 문서

> 현직자 자문 (2026-04-24) 기반 설계
> 학술 논문(Cerebro, DONAPI 등)으로 기술 근거 보강

---

## 1. 설계의 출발점 — 현직자 조언

### 1.1 조언 원문 요약

| 영역 | 현직자 조언 |
|---|---|
| **존재 확인의 가치** | "있는지 없는지만 판단하는 거라서 위험하다고도 말할 수 없다. 할루시네이션이니 재확인하세요 조언 수준." |
| **나이/인기 기반의 한계** | "오래된 거, 이런 거 기준으로는 약하다. 요즘 AI로 양산이 되거든. 새로운 것들이 엄청 핫해지고 사람들이 많이 쓰는 게 계속 생긴다." |
| **단순 키워드 매칭의 한계** | "몇 개의 키워드, 몇 개의 명령어, 평판, 오래된 거 이런 것만 가지고는 정확한 판단은 어려울 수 있다." |
| **핵심 방향** | "행위 기반으로 한다. 함수에 들어와서 딜리트가 되고 업로드가 되고 이런 일련의 절차를 분석해서 위험성을 경고한다." |
| **공신력 있는 기준** | "마이터 어택, 마이터 아틀라스, OWASP 같은 공신력 있는 데서 DB를 수집하고, 그걸 임베딩 벡터 DB로 순식간에 매칭한다." |
| **AI 적극 활용** | "클로드의 security-review, Gstack 같은 전문가 에이전트도 결국 AI가 하는 것. 프롬프트가 다를 뿐. 오히려 적극 활용해서 완성하는 게 나쁜 어프로치는 아니다." |
| **속도보다 정확도** | "빨리빨리 하는 게 중요한 게 아니라 제대로 하는 게 중요하다. 5분이 걸려도 10분이 걸려도 상관없다. 첫 분석 후 서버 저장하면 다음 사람은 순식간에 받는다." |
| **벤치마크 목표** | "axios처럼 수천만 다운로드 유명 패키지에서 취약점을 잡았다. 이거는 엄청난 가치다." |
| **Extension은 부가적** | "크롬 익스텐션, VS 코드 익스텐션 만드는 자체는 가치가 없다. 핵심 탐지 로직이 진짜 가치." |

### 1.2 설계에 반영한 결론

1. **판정 근거를 "행위"로 옮긴다** — 나이/인기/다운로드 수는 일절 사용하지 않음
2. **시퀀스 분석을 한다** — 단일 API가 아닌 행위 체인 순서를 본다
3. **공신력 있는 프레임워크로 매칭한다** — MITRE ATT&CK / ATLAS / OWASP LLM Top 10
4. **임베딩 벡터 DB로 매칭한다** — 정규식이 아닌 의미 기반 유사도 검색
5. **AI 심층 리뷰를 결합한다** — Claude Sonnet을 서버 내부에서 호출
6. **시간은 여유를 준다** — 첫 분석 느려도 됨, 서버 캐시로 다음부터 즉시
7. **유명 패키지에서 의심 근거를 찾을 수 있다** — 버전 간 행위 변화 분석

---

## 2. 판정 체계

### 2.1 근거 기반 판정 (점수가 아님)

위험도를 숫자로 만들지 않는다. 대신 **어떤 증거가 있는가** 로 설명한다.

```
Verdict ← {
  MALICIOUS   : MITRE 고위험 TTP 매칭 + LLM 확정
  HIGH_RISK   : MITRE 매칭 또는 버전 차이 의심 + LLM 의심
  SUSPICIOUS  : 단일 약한 시그널 + LLM 애매
  CLEAN       : 모든 검증 통과, 악성 근거 없음
  HALLUCINATION : 레지스트리 미등록 (탐지 불가, 재확인 안내)
}
```

리포트에는 항상 "**어떤 행위 시퀀스가 어떤 TTP와 매칭되었으며, LLM이 어떤 근거로 판단**" 이 담긴다.

### 2.2 출력 예시

```json
{
  "package": "example-pkg",
  "version": "1.2.3",
  "verdict": "HIGH_RISK",
  "findings": [
    {
      "type": "version_diff",
      "detail": "v1.2.2 → v1.2.3에서 requests.post, os.environ.get 호출 신규 추가",
      "files": ["example_pkg/__init__.py:42,47"]
    },
    {
      "type": "behavior_sequence",
      "sequence": "env_read → base64_encode → http_post",
      "mitre_ttp": "T1048 — Exfiltration Over Alternative Protocol",
      "confidence": 0.92
    }
  ],
  "llm_review": {
    "model": "claude-sonnet",
    "verdict": "suspicious",
    "comment": "새로 추가된 requests.post 호출이 외부 도메인으로 환경변수를 전송하는 패턴. 공식 기능 설명과 불일치."
  }
}
```

---

## 3. 시스템 아키텍처

```
Input: 패키지명 (+ 버전, 선택)
  ↓
[Stage 0] 존재 확인
  ├─ 레지스트리 미등록 → verdict: HALLUCINATION
  │   → "LLM 환각 가능성, 재확인 권장"
  └─ 등록됨 → Stage 1
  ↓
[Stage 1] Entry Point 추출
  ├─ PyPI : setup.py, pyproject.toml, __init__.py, __main__.py
  └─ npm  : package.json (scripts, main, bin), postinstall, index.js
  ↓
[Stage 2] Behavior Sequence 추출
  ├─ Tree-sitter AST 파싱
  ├─ 4 Attack Dimension API 호출 탐지
  │   ├─ Information Reading  : os.environ, fs.readFile, subprocess.check_output
  │   ├─ Encoding/Obfuscation : base64, compile, atob, btoa
  │   ├─ Payload Execution    : exec, eval, subprocess, spawn
  │   └─ Data Transmission    : requests, urllib, socket, fetch
  └─ 호출 순서 → 시퀀스 벡터
  ↓
[Stage 3] 버전 차이 분석 (axios급 공격 탐지)
  ├─ 이전 버전 N-1, N-3, N-5 아카이브 다운로드
  ├─ Entry Point AST 비교
  ├─ 새로 추가된 API 호출 식별
  └─ 위험 증가 패턴 감지
      ├─ 새 Network API + 외부 도메인 상수
      ├─ 새 Execute API
      ├─ 새 Encoding + Execute 조합
      └─ 새 파일 조작 (특히 crypto 관련)
  ↓
[Stage 4] MITRE TTP 매칭 (벡터 검색)
  ├─ MITRE ATT&CK + ATLAS + OWASP LLM Top 10 DB (사전 구축)
  ├─ Sentence-Transformer 임베딩
  ├─ pgvector / Qdrant 유사도 검색
  └─ Top-K TTP 매칭 + confidence
  ↓
[Stage 5] LLM 이중 검증
  ├─ Claude Sonnet API 호출 (서버 크레딧)
  ├─ 프롬프트 컨텍스트
  │   ├─ 추출된 Behavior Sequence
  │   ├─ 버전 차이 결과
  │   ├─ 매칭된 MITRE TTP
  │   └─ 코드 스니펫
  └─ LLM 판정 + 코멘트
  ↓
[Stage 6] 최종 Verdict
  ├─ findings 집계
  ├─ Verdict 결정
  └─ JSON + HTML 리포트 생성
  ↓
[Stage 7] 서버 캐시
  └─ 패키지+버전 키로 저장, 다음 사용자 즉시 반환
```

---

## 4. 부분 분석 전략 — "왜 이게 설득력 있는가"

### 4.1 Entry Point 집중 원칙

실증 연구에 따르면 악성 코드의 대부분이 **자동 실행 경로**에 있다.

| 위치 | 실행 시점 | 악성 사례 집중도 |
|---|---|---|
| `setup.py` | `pip install` 중 자동 | 약 50% 이상 |
| `package.json > scripts.postinstall` | `npm install` 중 자동 | 약 60% 이상 |
| `__init__.py` | `import` 시 자동 | 약 20% |
| `index.js` / `main` 엔트리 | `require` 시 자동 | 약 20% |
| `bin/*` | 직접 실행 | 약 5% |

공격자는 빠른 실행을 원하므로 **설치/import만 해도 실행되는 경로**를 주로 공략한다. 수백~수천 개 파일을 다 보는 것이 아니라 이 경로를 정밀 분석하는 것이 효율적이며, 실제 학술 연구(Cerebro)에서도 동일한 전략으로 PyPI 683개, npm 799개를 신규 탐지했다.

### 4.2 Tiered Analysis

```
Tier 1 — 항상 분석
  setup.py, pyproject.toml, package.json (scripts)
  __init__.py, __main__.py
  index.js, main 필드 파일

Tier 2 — Tier 1에서 의심 시 확장
  Tier 1이 import/require하는 모듈 1-hop
  bin/, scripts/, postinstall.js
  인코딩된 문자열 포함 파일

Tier 3 — Tier 1+2에서 고위험 시 심층
  Suspicious 파일 중 < 50KB 우선
  LLM에게 컨텍스트 포함 전체 리뷰 요청
```

### 4.3 설득 문장

> "전체 파일을 분석하지 않습니다. 대신 **실제 공격의 80% 이상이 집중되는 Entry Point** 를 AST 추출, MITRE TTP 매칭, LLM 3단 검증으로 정밀 분석합니다. 또한 **버전 차이 분석**으로 axios 사건처럼 합법 패키지에 주입된 공격까지 탐지합니다."

---

## 5. 예상 탐지 범위

### Tier A — 95%+

- 슬롭스쿼팅 (레지스트리 미등록)
- 타이포스쿼팅
- 설치 시 자동 실행 공격 (postinstall `curl | bash`, setup.py `exec`)
- credential 탈취 체인 (env_read → encode → http_post)

### Tier B — 80%+

- 난독화된 페이로드 (부분 디코딩)
- 서브모듈에 숨긴 악성 코드 (Tier 2)
- 변형된 알려진 공격 (벡터 유사도 매칭)
- **버전 차이 기반 의심 행위 주입 — event-stream, colors.js, eslint-scope, axios 등 실제 공급망 공격**

### Tier C — 40% (한계 명시)

- 완전히 새로운 공격 패턴 (MITRE에도 없음)
- 타임밤 / 로직밤 (정적 분석 한계)
- 네이티브 바이너리 공격 (.so, .dll)
- 사회공학 (코드 아닌 README 공격)

---

## 6. 구현 로드맵

### Phase 1 — 데이터 수집 (1~2주)

- [ ] MITRE ATT&CK JSON 수집 + 전처리
- [ ] MITRE ATLAS 전체 TTP
- [ ] OWASP Top 10 for LLM 매핑 테이블
- [ ] 악성 패키지 Ground Truth 50~100개
  - GHSA, Snyk, PyPI Safety DB
  - 실제 사건: event-stream, colors.js, eslint-scope, ua-parser-js, node-ipc, axios
- [ ] Entry Point 실증 통계 (샘플 기준)

### Phase 2 — Behavior Sequence 엔진 (2주)

- [ ] `detector/ast_parser.py` — tree-sitter Python/JS 통합
- [ ] `detector/api_catalog.py` — 4 Dimension + Cerebro 16 features + DONAPI 132 API
- [ ] `detector/sequence_extractor.py` — 호출 순서 추출
- [ ] `detector/entry_point.py` — Tier 1 파일 식별

### Phase 3 — 버전 차이 분석 (1주)

- [ ] `detector/version_diff.py`
- [ ] 이전 버전 N-1, N-3, N-5 자동 다운로드
- [ ] AST 비교 → 새 API 호출 추출
- [ ] 위험 증가 분류

### Phase 4 — MITRE 벡터 DB (2주)

- [ ] TTP 설명 → Sentence-Transformer 임베딩
- [ ] pgvector / Qdrant 인덱스
- [ ] 시퀀스 → 벡터 → Top-K 검색 API

### Phase 5 — LLM 이중 검증 (1주)

- [ ] Claude Sonnet API 서버 통합 (서버 비용 부담)
- [ ] 프롬프트 설계 (Sequence + Diff + MITRE 첨부)
- [ ] Rate limit + 캐시

### Phase 6 — 캐시 계층 (3일)

- [ ] PostgreSQL: 패키지+버전+결과
- [ ] Redis: hot cache
- [ ] 버전 변경 시 자동 재분석

### Phase 7 — 벤치마크 (1주)

- [ ] Ground Truth 50+50 → Precision/Recall
- [ ] 실제 사건 재현 테스트
- [ ] Claude 기본 `/security-review` vs 본 엔진 비교
- [ ] **목표: Claude 기본이 놓친 1건 이상을 본 엔진이 추가 탐지**

### Phase 8 — 클라이언트 재연결 (3일)

- [ ] FastAPI 엔드포인트
- [ ] Chrome/VSCode Extension에서 호출
- [ ] 결과 UI: MITRE 매핑 + 버전 차이 + LLM 코멘트 시각화

**총 예상: 10주**

---

## 7. 판정에 쓰지 않는 것 (중요)

본 엔진은 다음 정보를 **판정 근거로 사용하지 않는다.**

- 패키지 등록 경과일 / 최초 배포일
- 버전 개수
- 다운로드 수 / 인기도
- 유지관리자 계정 정보
- 정규식 단일 매칭 결과

이런 정보는 **참고용 메타데이터**로 리포트에 표시할 수 있지만, **위험도 판정에 영향을 주지 않는다.** 현직자가 지적했듯 AI로 양산되는 신규 패키지가 넘치는 환경에서 이런 신호는 구멍이 있기 때문이다.

---

## 8. 사용 기술 (요약)

| 영역 | 기술 |
|---|---|
| AST 파싱 | Tree-sitter (Python / JavaScript) |
| 특징 추출 | Cerebro 16 features, DONAPI 132 API 카탈로그 |
| 공격 패턴 DB | MITRE ATT&CK, MITRE ATLAS, OWASP LLM Top 10 |
| 임베딩 | Sentence-Transformers |
| 벡터 검색 | pgvector or Qdrant |
| LLM 검증 | Claude Sonnet API (Anthropic) |
| 저장소 | PostgreSQL + Redis |
| 서빙 | FastAPI |

세부 출처는 `references.md` 참고.

---

## 9. 다음 단계

- [x] 설계 확정
- [ ] Phase 1 착수 — Ground Truth 수집 + MITRE JSON 다운로드
- [ ] Entry Point 실증 통계 생성 (샘플 분석)
