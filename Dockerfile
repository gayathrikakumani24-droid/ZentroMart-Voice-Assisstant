# Multi-stage Dockerfile for ZentroMart VoiceOps
# Stage 1: Build the React + Vite frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Stage 2: Production Python Backend + Static UI
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application and dataset
COPY api/ ./api/
COPY src/ ./src/
COPY dataset/ ./dataset/

# Copy prebuilt React SPA bundle
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
