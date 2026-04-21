# 이메일 발송 템플릿

> `review_guide.md`와 함께 발송하거나, 본문으로 사용하세요.

---

## 제목 예시

```
[캡스톤 리뷰 요청] AI 슬롭스쿼팅 탐지기 프로젝트 검토 부탁드립니다
```

---

## 본문

안녕하세요, OOO님.

SEC-RESEARCH-LAB 7조에서 진행 중인 **AI 슬롭스쿼팅 탐지기** 프로젝트에 대한 코멘트를 부탁드리게 되어 연락드립니다.

### 프로젝트 요약

LLM(Claude, ChatGPT, Gemini 등)이 존재하지 않는 패키지명을 **환각(hallucinate)**하는 현상을 공격자가 악용하는 **슬롭스쿼팅 공급망 공격**을 실시간으로 탐지하는 도구입니다.

Chrome Extension, VSCode Extension, CLI, 자동화 워크플로우 네 가지 경로로 패키지를 분석하며, PyPI/npm 메타데이터(Layer 1)와 소스코드 아카이브 스트리밍(Layer 2) 2계층 판정 체계를 사용합니다.

### 첨부 자료

- **리뷰 가이드**: `review_guide.md` (실행 방법 + 테스트 시나리오 + 리뷰 포인트)
- **중간 보고서**: `midterm_report.pdf` / `midterm_report.docx`
- **GitHub**: https://github.com/yujin1103/Ai_Slopsquatting

### 리뷰 요청 범위

바쁘신 가운데 시간 내어주셔서 감사합니다. 검토 시간에 따라 아래 순서를 권장드립니다.

| 시간 | 권장 경로 |
|---|---|
| 10분 | `review_guide.md` 1~2장 + 구조도 확인 |
| 30분 | 위 + `midterm_report.pdf` + Chrome Extension 설치 테스트 |
| 1시간+ | 위 + 핵심 코드 리뷰 (`source_analyzer.py`, 점수 산출 로직) |

특히 아래 부분에 대한 피드백이 큰 도움이 될 것 같습니다.

1. **위험도 산정 로직의 타당성**
   - Layer 1/2 가중치 설정 (`secure_capstone/api/main.py`)
   - 신뢰도 할인 계수 (pandas 같은 장기 패키지 오탐 방지)

2. **소스코드 분석 패턴의 완전성**
   - 악성 패턴 9종 (`secure_capstone/source_analyzer.py`)
   - 추가 고려해야 할 공격 패턴

3. **시스템 확장성**
   - Chrome Extension + VSCode Extension + CLI 구조
   - Cargo(Rust) 등 추가 에코시스템 지원 방향

### 실행 환경

- Docker Desktop 필요 (API 서버용)
- Chrome 최신 버전 (Extension용)
- 상세 설치 방법은 `review_guide.md` 3장 참고

### 문의

리뷰 중 질문이나 피드백이 있으시면 언제든지 회신 부탁드립니다. 시간 내어주셔서 진심으로 감사합니다.

감사합니다.

---

SEC-RESEARCH-LAB 7조  
AI 슬롭스쿼팅 탐지기 프로젝트 팀

- 이동건 (AI 입력 처리 / 패키지 파서)
- 강한승 (위험도 분석 엔진)
- 김지혜 (CLI / 리포트)
- 정은 (시스템 통합 / Extension)
