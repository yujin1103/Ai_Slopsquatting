FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# build context = secure_capstone/ 이므로 api/requirements.txt 경로
COPY api/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# api 소스 복사
COPY api/ .

# source_analyzer.py 복사 (secure_capstone/ 루트에 있음)
COPY source_analyzer.py .

# main.py의 sys.path.insert(0, parent.parent) 가 /를 가리키므로
# source_analyzer.py를 /app 에도 두면 직접 import 가능하게 수정
# → 이미 WORKDIR /app 이므로 from source_analyzer import ... 바로 동작

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
