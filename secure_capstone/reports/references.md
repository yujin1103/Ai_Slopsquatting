# V2 설계 참고 문헌 (References)

> V2 재설계 과정에서 참조한 학술 논문, 산업 보고서, 공공 프레임워크 목록.  
> 최종 업데이트: 2026-04-24

---

## 1. 핵심 학술 논문 (Academic Papers)

### 1.1 Cerebro — 본 프로젝트의 주요 참고 모델

> **Killing Two Birds with One Stone: Malicious Package Detection in NPM and PyPI using a Single Model of Malicious Behavior Sequence**
> 
> - **저자**: Junan Zhang, Kaifeng Huang, Yiheng Huang, Bihuan Chen, Ruisi Wang, Chong Wang, Xin Peng
> - **발표**: ACM Transactions on Software Engineering and Methodology (TOSEM), 2025
> - **arXiv**: https://arxiv.org/abs/2309.02637
> - **HTML 전문**: https://arxiv.org/html/2309.02637v2
> - **PDF**: https://arxiv.org/pdf/2309.02637
> - **ACM**: https://dl.acm.org/doi/10.1145/3705304
> - **ResearchGate**: https://www.researchgate.net/publication/373715331

**V2에서 차용한 개념:**
- 16개 feature를 AST로 추출하여 Behavior Sequence 생성
- Tree-sitter를 활용한 Python/JavaScript 통합 파싱
- 4가지 Attack Dimension (Information Reading / Data Transmission / Encoding / Payload Execution)
- Entry Point 중심 부분 분석

**성과:** PyPI 683개, npm 799개 신규 악성 패키지 탐지, 공식 운영팀으로부터 385건의 감사 메일 수신.

---

### 1.2 DONAPI — 행위 시퀀스 지식 매핑

> **Donapi: Malicious NPM Packages Detector using Behavior Sequence Knowledge Mapping**
> 
> - **발표**: USENIX Security Symposium 2024
> - **USENIX**: https://www.usenix.org/system/files/sec24fall-prepub-171-huang-cheng.pdf
> - **Final PDF**: https://www.usenix.org/system/files/usenixsecurity24-huang-cheng.pdf
> - **arXiv**: https://arxiv.org/html/2403.08334v1

**V2에서 차용한 개념:**
- 132개 native API 모니터링 (파일 조작 / 네트워크 / 프로세스 생성)
- 12 behavior types + 40 behavior subtypes 분류 체계
- AST 기반 API 호출 순서 추적

---

### 1.3 PyPI 악성 코드 실증 연구

> **An Empirical Study of Malicious Code In PyPI Ecosystem**
> 
> - **PDF**: https://lcwj3.github.io/img_cs/pdf/An%20Empirical%20Study%20of%20Malicious%20Code%20In%20PyPI%20Ecosystem.pdf

**V2에서 차용한 인사이트:**
- PyPI 악성 코드의 파일 분포 실증 데이터
- setup.py가 공격 루트의 대부분을 차지한다는 근거
- Entry Point 중심 탐지 전략의 실증 근거

---

### 1.4 메타데이터 기반 악성 패키지 탐지

> **Malicious Package Detection using Metadata Information**
> 
> - **arXiv**: https://arxiv.org/abs/2402.07444
> - **PDF**: https://arxiv.org/pdf/2402.07444

**V2에서 차용한 개념:**
- Layer 1 메타데이터 분석의 한계 확인
- 메타데이터 단독으로는 정확한 판단이 어렵다는 연구 근거 (현직자 피드백 뒷받침)

---

### 1.5 구문 코드 표현 기반 악성 스크립트 탐지

> **SCORE: Syntactic Code Representations for Static Script Malware Detection**
> 
> - **arXiv HTML**: https://arxiv.org/html/2411.08182v1

**V2에서 차용한 개념:**
- AST 표현 기반 정적 분석의 효과성
- 스크립트 기반 악성코드 탐지에서의 구문 표현 중요성

---

### 1.6 머신러닝 기반 PyPI 악성 패키지 탐지

> **A Machine Learning-Based Approach For Detecting Malicious PyPI Packages**
> 
> - **ResearchGate**: https://www.researchgate.net/publication/386555242

**V2에서 차용한 개념:**
- ML 기반 feature engineering 접근 방식
- 정적 분석 + 분류기 조합의 효과성

---

## 2. 산업 보고서 및 블로그 (Industry Reports)

### 2.1 Datadog Security Labs — MUT-8964 캠페인 분석

> **MUT-8964: An NPM and PyPI Malicious Campaign Targeting Windows Users**
> 
> - URL: https://securitylabs.datadoghq.com/articles/mut-8964-an-npm-and-pypi-malicious-campaign-targeting-windows-users/

**V2에서 차용한 인사이트:**
- setup.py에서 PowerShell을 호출해 infostealer 다운로드하는 실제 공격 사례
- npm postinstall hook에서 credential harvesting script 주입 사례
- **"pip install / npm install이 import보다 먼저 실행된다"**는 공격 루트의 중요성

### 2.2 Datadog Security Labs — macOS 타겟 PyPI

> **Malicious PyPI packages targeting highly specific MacOS machines**
> 
> - URL: https://securitylabs.datadoghq.com/articles/malicious-pypi-package-targeting-highly-specific-macos-machines/

**V2에서 차용한 인사이트:**
- 패키지별 타겟팅 공격의 다양성
- Entry Point 분석이 필요한 이유

### 2.3 The Hacker News — 공급망 공격 동향

> **Malicious PyPI and npm Packages Discovered Exploiting Dependencies in Supply Chain Attacks**
> 
> - URL: https://thehackernews.com/2025/08/malicious-pypi-and-npm-packages.html

### 2.4 Sonatype — 실제 악성 패키지 사례집

> **Top 8 Malicious Packages Recently Found on PyPI**
> 
> - URL: https://www.sonatype.com/blog/top-8-malicious-attacks-recently-found-on-pypi

**V2에서 차용한 인사이트:**
- Ground Truth 데이터 수집 소스
- 실제 공격 패턴의 다양성

### 2.5 GitGuardian — 48시간 캠페인 분석

> **No Off Season: Three Supply Chain Campaigns Hit npm, PyPI, and Docker Hub in 48 Hours**
> 
> - URL: https://blog.gitguardian.com/three-supply-chain-campaigns-hit-npm-pypi-and-docker-hub-in-48-hours/

### 2.6 Security Scientist — 타이포스쿼팅 Q&A

> **12 Questions and Answers About Typosquatting (PyPI/NPM)**
> 
> - URL: https://www.securityscientist.net/blog/12-questions-and-answers-about-typosquatting-pypi-npm-supply-chain/

---

## 3. 공공 프레임워크 및 표준 (Public Frameworks)

### 3.1 MITRE ATT&CK

> **MITRE ATT&CK — 사이버 공격 전술/기술/절차(TTP) 지식베이스**
> 
> - 공식: https://attack.mitre.org/
> - JSON 데이터: https://github.com/mitre/cti

**V2 활용 계획:**
- TTP(T-code) 식별자를 분석 리포트에 매핑
- 예: T1486 (Data Encrypted for Impact), T1059 (Command and Scripting Interpreter), T1552 (Unsecured Credentials)
- 설명 텍스트를 Sentence-Transformer로 임베딩 → 벡터 DB 구축

### 3.2 MITRE ATLAS

> **MITRE ATLAS — AI 시스템을 겨냥한 적대적 위협 정보**
> 
> - 공식: https://atlas.mitre.org/

**V2 활용 계획:**
- AI/LLM 관련 공격 TTP 확장
- 슬롭스쿼팅 문맥에서의 적용

### 3.3 OWASP Top 10 for Large Language Model Applications

> **OWASP Top 10 for LLM Applications (2025)**
> 
> - 공식: https://owasp.org/www-project-top-10-for-large-language-model-applications/

**V2 활용 계획:**
- LLM 특화 취약점 카테고리 매핑
- LLM01 Prompt Injection, LLM05 Supply Chain 등

### 3.4 GitHub Advisory Database (GHSA)

> **GitHub Security Advisory Database**
> 
> - 공식: https://github.com/advisories

**V2 활용 계획:**
- Ground Truth 데이터 수집 (양성 샘플)
- 공개된 악성 패키지의 메타정보

### 3.5 PyPI Safety Database

> **PyPI Safety DB — 알려진 취약 Python 패키지 목록**
> 
> - 공식: https://github.com/pyupio/safety-db

### 3.6 Snyk Vulnerability Database

> **Snyk — 상용 취약점 DB (무료 조회)**
> 
> - 공식: https://security.snyk.io/

### 3.7 npm Security Advisories

> **npm Advisory DB**
> 
> - 공식: https://www.npmjs.com/advisories

---

## 4. 기술 도구 (Technical Tools)

### 4.1 Tree-sitter

> **Tree-sitter — 증분 파싱 라이브러리**
> 
> - 공식: https://tree-sitter.github.io/tree-sitter/
> - GitHub: https://github.com/tree-sitter/tree-sitter

**V2 활용:** Python/JavaScript를 AST로 파싱하고 쿼리로 구문 패턴 매칭.

### 4.2 Sentence-Transformers

> **Sentence-Transformers — 문장 임베딩 모델**
> 
> - 공식: https://www.sbert.net/

**V2 활용:** MITRE TTP 설명 + 우리 시퀀스의 의미 기반 벡터 표현.

### 4.3 pgvector / Qdrant

> **pgvector** — PostgreSQL 벡터 확장
> - GitHub: https://github.com/pgvector/pgvector
> 
> **Qdrant** — 벡터 검색 엔진
> - 공식: https://qdrant.tech/

**V2 활용:** TTP 임베딩 저장 및 시퀀스-TTP 유사도 검색.

### 4.4 Claude Code Security Review

> **Claude Code `/security-review` 기능**
> 
> - Anthropic 문서: https://docs.anthropic.com/en/docs/build-with-claude
> - Claude Code GitHub Action: https://github.com/anthropics/claude-code-action

**V2 활용:** LLM 이중 검증 레이어로 활용. 우리 엔진 + Claude 리뷰 결과 결합.

---

## 5. 관련 커뮤니티 및 도구

### 5.1 Emergent Mind — 악성 오픈소스 패키지 탐지 연구 동향

> URL: https://www.emergentmind.com/topics/malicious-open-source-package-detection

### 5.2 Socket (상용)

> - 공식: https://socket.dev/
> - 블로그: https://socket.dev/blog

**참고:** 본 프로젝트의 경쟁 도구. 메타데이터 중심 탐지로 L2 소스 분석은 제한적.

### 5.3 Snyk (상용)

> - 공식: https://snyk.io/
> - 관련 블로그: https://snyk.io/articles/package-hallucinations/

### 5.4 Aikido Security (상용)

> - 블로그: https://www.aikido.dev/blog/slopsquatting-ai-package-hallucination-attacks

---

## 6. 본 프로젝트와 기존 연구의 차별점

| 항목 | 기존 연구 (Cerebro, DONAPI 등) | 본 프로젝트 V2 |
|---|---|---|
| 타겟 사용자 | 연구자, 레지스트리 운영자 | **개발자 (AI 보조 개발 시)** |
| 탐지 시점 | 레지스트리 업로드 후 배치 스캔 | **AI 응답 생성 시점 실시간** |
| UI 연동 | 연구 결과 리포트 | **Chrome/VSCode Extension 인라인** |
| 분석 엔진 | 단일 (정적 or ML) | **정적 분석 + MITRE 벡터 검색 + LLM 이중 검증** |
| 슬롭스쿼팅 특화 | 없음 (일반 악성 패키지) | **LLM 환각 패키지 탐지 포함** |

---

## 7. 인용 시 포맷 (BibTeX 예시)

```bibtex
@article{cerebro2025,
  title={Killing Two Birds with One Stone: Malicious Package Detection in NPM and PyPI using a Single Model of Malicious Behavior Sequence},
  author={Zhang, Junan and Huang, Kaifeng and Huang, Yiheng and Chen, Bihuan and Wang, Ruisi and Wang, Chong and Peng, Xin},
  journal={ACM Transactions on Software Engineering and Methodology},
  year={2025},
  publisher={ACM},
  doi={10.1145/3705304}
}

@inproceedings{donapi2024,
  title={Donapi: Malicious NPM Packages Detector using Behavior Sequence Knowledge Mapping},
  booktitle={USENIX Security Symposium},
  year={2024}
}
```

---

## 8. 추가 수집이 필요한 자료

V2 Phase 1에서 추가로 수집할 자료:

- [ ] MITRE ATT&CK Enterprise Matrix JSON (최신 버전)
- [ ] MITRE ATLAS 전체 TTP 목록
- [ ] OWASP LLM Top 10 2025 공식 PDF
- [ ] 최근 1년(2025-2026) 악성 PyPI 패키지 Top 100 샘플
- [ ] 최근 1년 악성 npm 패키지 Top 100 샘플
- [ ] axios, colors.js, event-stream 등 실제 공급망 공격 사례 분석 보고서
