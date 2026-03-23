"""
멀티 LLM 클라이언트
GPT-4o, Claude, Gemini에 동일한 인터페이스로 질의
- 자동 재시도 (지수 백오프)
- 속도 제한 대응
- 응답에서 패키지명 추출
"""

import asyncio
import re
import time
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# LLM 프롬프트: 패키지명을 명확히 표기하도록 유도
SYSTEM_PROMPT = """You are a helpful programming assistant with deep knowledge of software packages and libraries.
When recommending packages, always:
1. Provide the exact package name as it would be installed (e.g., `pip install package-name` or `npm install package-name`)
2. Use backticks around package names
3. Include the install command when relevant
Be specific and recommend real packages that exist."""

def build_user_prompt(question: str) -> str:
    return f"""{question}

Please provide specific package recommendations with exact names I can install.
Format package names in backticks and include install commands where possible."""


@dataclass
class LLMResponse:
    model: str
    question_id: int
    run_number: int
    raw_text: str
    packages: List[str]
    tokens_used: int
    latency_ms: int
    error: Optional[str] = None


def extract_packages(text: str, max_packages: int = 8) -> List[str]:
    """LLM 응답 텍스트에서 패키지명 추출"""
    found = set()

    # 패턴 1: 백틱으로 감싼 패키지명 `package-name`
    for m in re.finditer(r'`([a-zA-Z0-9][a-zA-Z0-9_\-\.]{1,60})`', text):
        found.add(m.group(1).strip())

    # 패턴 2: pip install package-name
    for m in re.finditer(r'pip install\s+([\w\-\.]+)', text, re.IGNORECASE):
        found.add(m.group(1).strip())

    # 패턴 3: npm install package-name
    for m in re.finditer(r'npm install\s+([\w\-\.\/@]+)', text, re.IGNORECASE):
        pkg = m.group(1).strip()
        # scoped 패키지 (@org/pkg) 유지, 플래그 제거
        if not pkg.startswith('-'):
            found.add(pkg)

    # 패턴 4: $ pip/npm 명령어 블록
    for m in re.finditer(r'(?:pip|npm)\s+install\s+([\w\-\.\/\@]+)', text, re.IGNORECASE):
        pkg = m.group(1).strip()
        if not pkg.startswith('-'):
            found.add(pkg)

    # 불용어 필터링 (일반 영어 단어, 너무 짧거나 긴 이름)
    stopwords = {
        'the', 'and', 'for', 'with', 'that', 'this', 'from', 'can', 'you',
        'use', 'your', 'will', 'not', 'are', 'have', 'more', 'any', 'all',
        'it', 'is', 'in', 'or', 'as', 'an', 'to', 'a', 'be', 'has',
        'pip', 'npm', 'install', 'python', 'node', 'js', 'py',
    }
    cleaned = [
        p for p in found
        if p.lower() not in stopwords
        and 2 <= len(p) <= 80
        and not p.isdigit()
        and re.match(r'^[@a-zA-Z0-9]', p)
    ]

    return cleaned[:max_packages]


# ─────────────────────────────────────────────────────
# OpenAI (GPT-4o)
# ─────────────────────────────────────────────────────
async def query_openai(
    question_id: int,
    question_text: str,
    run_number: int,
    api_key: str,
    model: str = "gpt-4o",
    max_packages: int = 8,
    max_retries: int = 3,
) -> LLMResponse:
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return LLMResponse(
            model=model, question_id=question_id, run_number=run_number,
            raw_text="", packages=[], tokens_used=0, latency_ms=0,
            error="openai 패키지가 설치되지 않았습니다. pip install openai"
        )

    client = AsyncOpenAI(api_key=api_key)
    last_error = None

    for attempt in range(max_retries):
        try:
            start = time.monotonic()
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(question_text)},
                ],
                temperature=0.7,
                max_tokens=600,
            )
            latency = int((time.monotonic() - start) * 1000)
            raw = resp.choices[0].message.content or ""
            return LLMResponse(
                model=model,
                question_id=question_id,
                run_number=run_number,
                raw_text=raw,
                packages=extract_packages(raw, max_packages),
                tokens_used=resp.usage.total_tokens if resp.usage else 0,
                latency_ms=latency,
            )
        except Exception as e:
            last_error = str(e)
            wait = 2 ** attempt
            logger.warning(f"[OpenAI] 재시도 {attempt+1}/{max_retries} (Q{question_id}): {e}")
            await asyncio.sleep(wait)

    return LLMResponse(
        model=model, question_id=question_id, run_number=run_number,
        raw_text="", packages=[], tokens_used=0, latency_ms=0,
        error=last_error,
    )


# ─────────────────────────────────────────────────────
# Anthropic (Claude)
# ─────────────────────────────────────────────────────
async def query_anthropic(
    question_id: int,
    question_text: str,
    run_number: int,
    api_key: str,
    model: str = "claude-3-5-sonnet-20241022",
    max_packages: int = 8,
    max_retries: int = 3,
) -> LLMResponse:
    try:
        import anthropic
    except ImportError:
        return LLMResponse(
            model=model, question_id=question_id, run_number=run_number,
            raw_text="", packages=[], tokens_used=0, latency_ms=0,
            error="anthropic 패키지가 설치되지 않았습니다. pip install anthropic"
        )

    client = anthropic.AsyncAnthropic(api_key=api_key)
    last_error = None

    for attempt in range(max_retries):
        try:
            start = time.monotonic()
            resp = await client.messages.create(
                model=model,
                max_tokens=600,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_prompt(question_text)}],
            )
            latency = int((time.monotonic() - start) * 1000)
            raw = resp.content[0].text if resp.content else ""
            return LLMResponse(
                model=model,
                question_id=question_id,
                run_number=run_number,
                raw_text=raw,
                packages=extract_packages(raw, max_packages),
                tokens_used=(resp.usage.input_tokens + resp.usage.output_tokens),
                latency_ms=latency,
            )
        except Exception as e:
            last_error = str(e)
            wait = 2 ** attempt
            logger.warning(f"[Anthropic] 재시도 {attempt+1}/{max_retries} (Q{question_id}): {e}")
            await asyncio.sleep(wait)

    return LLMResponse(
        model=model, question_id=question_id, run_number=run_number,
        raw_text="", packages=[], tokens_used=0, latency_ms=0,
        error=last_error,
    )


# ─────────────────────────────────────────────────────
# Google Gemini
# ─────────────────────────────────────────────────────
async def query_gemini(
    question_id: int,
    question_text: str,
    run_number: int,
    api_key: str,
    model: str = "gemini-2.0-flash",
    max_packages: int = 8,
    max_retries: int = 3,
) -> LLMResponse:
    try:
        import google.generativeai as genai
    except ImportError:
        return LLMResponse(
            model=model, question_id=question_id, run_number=run_number,
            raw_text="", packages=[], tokens_used=0, latency_ms=0,
            error="google-generativeai 패키지가 설치되지 않았습니다. pip install google-generativeai"
        )

    genai.configure(api_key=api_key)
    last_error = None

    for attempt in range(max_retries):
        try:
            start = time.monotonic()
            gemini_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=SYSTEM_PROMPT,
            )
            # Gemini SDK의 generate_content는 동기이므로 executor에서 실행
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: gemini_model.generate_content(
                    build_user_prompt(question_text),
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=600,
                    ),
                )
            )
            latency = int((time.monotonic() - start) * 1000)
            raw = resp.text if resp.text else ""
            tokens = 0
            if hasattr(resp, 'usage_metadata') and resp.usage_metadata:
                tokens = getattr(resp.usage_metadata, 'total_token_count', 0)
            return LLMResponse(
                model=model,
                question_id=question_id,
                run_number=run_number,
                raw_text=raw,
                packages=extract_packages(raw, max_packages),
                tokens_used=tokens,
                latency_ms=latency,
            )
        except Exception as e:
            last_error = str(e)
            wait = 2 ** attempt
            logger.warning(f"[Gemini] 재시도 {attempt+1}/{max_retries} (Q{question_id}): {e}")
            await asyncio.sleep(wait)

    return LLMResponse(
        model=model, question_id=question_id, run_number=run_number,
        raw_text="", packages=[], tokens_used=0, latency_ms=0,
        error=last_error,
    )


# ─────────────────────────────────────────────────────
# 통합 디스패처
# ─────────────────────────────────────────────────────
async def query_llm(
    question_id: int,
    question_text: str,
    run_number: int,
    model_name: str,
    config,
) -> LLMResponse:
    """모델 이름에 따라 적절한 LLM 클라이언트 호출"""
    if "gpt" in model_name.lower():
        return await query_openai(
            question_id, question_text, run_number,
            api_key=config.openai_api_key,
            model=config.openai_model,
            max_packages=config.max_packages_per_response,
        )
    elif "claude" in model_name.lower():
        return await query_anthropic(
            question_id, question_text, run_number,
            api_key=config.anthropic_api_key,
            model=config.anthropic_model,
            max_packages=config.max_packages_per_response,
        )
    elif "gemini" in model_name.lower():
        return await query_gemini(
            question_id, question_text, run_number,
            api_key=config.google_api_key,
            model=config.google_model,
            max_packages=config.max_packages_per_response,
        )
    else:
        return LLMResponse(
            model=model_name, question_id=question_id, run_number=run_number,
            raw_text="", packages=[], tokens_used=0, latency_ms=0,
            error=f"지원하지 않는 모델: {model_name}",
        )
