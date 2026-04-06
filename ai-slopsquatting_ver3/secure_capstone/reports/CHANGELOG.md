# 변동사항 정리 (2026-04-04)

> 기준 커밋: `6ada629` → `a7d0f87`
> 작업 범위: 소스코드 분석 모듈 추가 / 연구 파이프라인 개선 / 파서 정확도 향상

---

## 1. 위협 모델 재정의

### 변경 전
- LLM이 추천한 패키지가 PyPI/npm에 **없으면** 위험으로 판단
- 소스코드는 분석하지 않음

### 변경 후
- **"등록되어 있지만 악의적인 패키지"** 탐지에 집중
- PyPI/npm은 업로드 시 코드 리뷰가 없음 → 공격자 등록 후 삭제까지의 시간 창이 실제 공격 기회
- 연구 모듈(환각 측정)과 API 모듈(악성 탐지)의 역할을 명확히 분리

```
패키지명 입력
    │
    ▼
Layer 1: 존재 확인 (메타데이터)
    ├─ 미등록 → CRITICAL (소스 분석 불가)
    └─ 등록됨 → Layer 2
              ▼
         Layer 2: 소스코드 분석
              아카이브 메모리 스트리밍 (다운로드/설치 없음)
              악성 패턴 9종 탐지
              ▼
         최종 판정: CRITICAL / HIGH / MEDIUM / LOW
```

---

## 2. 신규 파일

### `secure_capstone/source_analyzer.py` (514줄)
PyPI/npm 패키지 소스코드를 **다운로드/설치 없이** HTTP 스트리밍으로 메모리에서 분석하는 공용 모듈.

| 항목 | 내용 |
|------|------|
| 아카이브 방식 | `.tar.gz` / `.whl` / `.tgz` → BytesIO 메모리 스트리밍 |
| 크기 제한 | 5MB 초과 시 스킵 |
| 분석 대상 파일 | `setup.py`, `__init__.py`, `__main__.py`, `index.js`, `postinstall.js` 등 |

**탐지 패턴 9종:**

| 카테고리 | 점수 | 탐지 내용 |
|---|:---:|---|
| `install_hook` | +20 | `setup.py` `cmdclass` 오버라이드 |
| `exec_eval` | +15 | `exec()`, `eval()`, `compile()` |
| `base64_exec` | +25 | base64 디코딩 + exec 조합 |
| `credential_theft` | +25 | `os.environ` + `requests.post` 조합 |
| `shell_execution` | +15 | `subprocess`, `os.system`, `curl`/`wget` |
| `obfuscated_import` | +10 | `__import__('os')`, getattr import 체인 |
| `network_access` | +10 | `socket`, `urllib` 직접 사용 |
| `npm_install_script` | +25 | `postinstall`에 `curl`/`eval` 사용 |
| `high_entropy_string` | +10 | Shannon 엔트로피 > 4.5 (난독화 의심) |

- 카테고리당 중복 점수 없음, 최종 점수 100점 상한
- 소스 분석 실패 시 기존 파이프라인에 영향 없음 (예외 무시, score 0)

---

### `CLAUDE.md`
프로젝트 전체 구조, 위협 모델, Layer 파이프라인 설계, TODO를 문서화.

### `.gitignore`
| 제외 항목 | 이유 |
|---|---|
| `.env` | API 키 노출 방지 |
| `*.db` | 실험 DB (재생성 가능) |
| `__pycache__/` | 바이너리 캐시 |
| `.claude/` | 도구 내부 파일 |
| `json_qa_*/` | 개별 실험 JSON 200개+ (대용량) |

### `reports/architecture_diagram.html`
현재 구현 기준 시스템 아키텍처 다이어그램.
사용자 흐름: `개발자 → 소스 파일 → slop_check.py CLI → FastAPI (Docker :8001) → PyPI/npm`

### `reports/gpt4o_research_report.md`
GPT-4o 실험 결과 마크다운 리포트 (아래 **5번 항목** 참고).

---

## 3. 수정된 파일

### `api/main.py`
- `PackageResult` 모델에 필드 추가: `risk_layer`, `metadata_score`, `source_analyzed`, `source_score`, `source_signals`
- `_analyse_package()` 내 레지스트리 데이터 보존 → `analyze_package_source()` 호출
- **Layer 기반 최종 점수 계산 로직 적용**
  - 미등록 패키지 → Layer 1 (메타데이터 점수만)
  - 등록 패키지 → Layer 2 (소스 분석 점수 + 메타데이터 보조 가중치)

### `research/llm_client.py` — 파서 정확도 개선

**문제:** 백틱 패턴이 코드 예제의 변수명, 서브모듈 경로, 클래스명을 패키지명으로 오인식

**오검출 사례:**

| 이름 | 실제 정체 | 원인 |
|---|---|---|
| `your_app_file_name` | placeholder | `` `python your_app_file_name.py` `` |
| `your_script_name` | placeholder | 코드 예제 |
| `torch.quantization` | torch 서브모듈 | 속성 접근 경로 |
| `torch.onnx.export` | torch 함수 | 속성 접근 경로 (3단계) |
| `pytorch_lightning.loggers` | pl 서브모듈 | 속성 접근 경로 |
| `MLFlowLogger` | 클래스명 | PascalCase, 설치 커맨드 미등장 |
| `ImageDataGenerator` | 클래스명 | PascalCase |
| `dummy_input` | 변수명 | `torch.onnx.export(model, dummy_input, ...)` |

**추가된 필터 3종:**

1. **Placeholder 필터**
   `your_*`, `my_*`, `dummy_*`, `foo_*`, `example_*` 로 시작하거나
   `*_name`, `*_file`, `*_path`, `*_input`, `*_output`, `*_model` 로 끝나는 이름 제거

2. **서브모듈 경로 필터**
   `.` 을 포함하는 이름 전부 제거 (npm scoped `@org/pkg` 예외)
   → `torch.quantization`, `os.path`, `pytorch_lightning.loggers` 등 제거

3. **클래스명 필터** (백틱 출처에만 적용, `pip install` 출처 제외)
   PascalCase (`ImageDataGenerator`) 및 대문자 접두사 CamelCase (`MLFlowLogger`) 제거

**추가 개선:**
- `pip install` / `npm install` 출처 이름 우선 처리 (신뢰도 높음)
- stopwords 확장: `model`, `data`, `input`, `output`, `bash`, `here` 등 추가
- 파일 확장자 포함 이름 필터 (`.py`, `.json`, `.pkl` 등)

### `research/database.py`
- `get_full_qa_data()` 추가: 모든 실험의 질문 + 원본 답변 + 패키지 검증 결과를 JSON 리포트용으로 반환

### `research/analyzer.py`
- `generate_json_report(db, output_path)` 추가
  - 출력 구조: `meta` + `summary` + `stats` (모델별/도메인별/위험도별) + `experiments` 배열

### `research/pipeline.py`
- `_save_experiment_json()` 추가: 실험별 개별 JSON 파일 저장 (`q{id}_{model}_run{n}.json`)
- `process_one()`: `json_dir` 파라미터 추가, 실험 후 JSON 파일 저장
- `run_pipeline()`: 타임스탬프 기반 `json_qa_{timestamp}/` 디렉토리 생성, 파이프라인 완료 후 전체 summary JSON 자동 생성
- `cmd_json_report()` 추가 + `json-report` CLI 커맨드 지원

### `research/validator.py`
- 소스 분석 의존성 **완전 제거** (research 모듈은 존재 여부 확인만 담당)
- `PackageInfo` 단순화: `source_*` 필드 제거
- `_calculate_risk()`: 메타데이터 기반 순수 할루시네이션 판정으로 복귀

---

## 4. 삭제된 파일

| 파일 | 이유 |
|---|---|
| `reports/slop_report_2026-03-14T*.html` (6개) | 구버전 리포트, 내용 불필요 |

---

## 5. GPT-4o 실험 결과 (`reports/gpt4o_research_report.md`)

**실험 설정**
- 모델: GPT-4o
- 질문: 20개 (python_ml 도메인)
- 반복: 5회 / 질문
- 총 호출: 100회

**파서 개선 전후 비교**

| 항목 | 개선 전 | 개선 후 |
|---|:---:|:---:|
| 추출 패키지 수 | 387개 | 358개 |
| 할루시네이션 수 | 43개 | **19개** |
| 할루시네이션율 | 11.1% | **5.3%** |
| 오검출 제거 | - | 24개 |

> 오검출 24개: 파서가 변수명/클래스명/서브모듈을 패키지로 인식 → 당연히 PyPI 미등록 → 할루시네이션으로 잘못 집계된 것

**할루시네이션 상위 질문 (정제 후)**

| 질문 | 할루시네이션 수 | 비율 |
|---|:---:|:---:|
| Q08. Knowledge distillation (BERT) | 5개 | 36% |
| Q12. Continual learning (catastrophic forgetting) | 4개 | 22% |
| Q13. Multi-armed bandit algorithms | 3개 | 18% |
| Q11. Gradient-based NAS | 3개 | 17% |

> 틈새/신흥 분야일수록 GPT-4o가 존재하지 않는 패키지를 더 많이 추천

---

## 6. DB 정리

- Anthropic API 키 인증 실패로 발생한 오류 실험 23건 삭제
  - `experiments` 테이블: 23행 삭제
  - `packages` 테이블: 관련 행 삭제
- GPT-4o 실험 100건만 유지
