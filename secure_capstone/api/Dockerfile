# Python 3.11 slim 기반 (가볍게)
FROM python:3.11-slim

# 시스템 패키지 설치 방지 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 작업 폴더 설정
WORKDIR /app

# 의존성 먼저 복사 (캐시 효율 최대화)
COPY requirements.txt .

# 패키지 설치
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# FastAPI 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
