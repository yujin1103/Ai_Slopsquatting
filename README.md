# ai_Slopsquatting

04.04 chrome extension 추가

vscode 에서 slopsquatting 폴더를 열어 docker compose up -d로 docker 실행 시킨 후 chrome://extensions 들어가셔서 압축 해제된 확장 프로그램 로드 누르신다음 slop-detector-extension 폴더 선택하고 켜시면 데모버전 실행 가능합니다

gemini gpt claude 3가지 llm을 타겟으로 했고 3개의 llm 공용과 각 모델마다 따로 분류하여 해봤습니다(설명이 부족하여 ai에게 물어보시면 좋을 것 같아요). 

claude는 아티팩트로 내놓는 경우가 많아 코드 블럭과 아티팩트 블럭으로 내놓게 하려고 수정중에 있습니다.

content/

├── common.js      ← 공통 유틸

├── claude.js      ← 코드블록 감지 (claude.ai)

├── artifact.js    ← 아티팩트 iframe 감지

├── chatgpt.js     ← div[dir='ltr'] 감지

└── gemini.js      ← pre code 감지
