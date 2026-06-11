FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 루트 requirements.txt (ai-pipeline 포함)
COPY requirements.txt /tmp/root_requirements.txt
RUN pip install --no-cache-dir -r /tmp/root_requirements.txt

# 백엔드 requirements.txt
COPY backend/requirements.txt /tmp/backend_requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend_requirements.txt

# 운영 이미지에 코드 굽기. dev compose는 볼륨 마운트로 이 코드를 덮어쓰므로
# 개발 hot-reload에는 영향 없음. prod compose는 볼륨 없이 이 코드를 그대로 실행.
COPY backend /workspace/backend
COPY ai-pipeline /workspace/ai-pipeline
COPY crawling /workspace/crawling

WORKDIR /workspace/backend
ENV PYTHONPATH=/workspace/backend:/workspace/ai-pipeline:/workspace/crawling/steam

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
