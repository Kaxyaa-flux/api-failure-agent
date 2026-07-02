FROM node:20-alpine AS frontend-builder
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm ci --silent
COPY dashboard/ ./
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY --from=frontend-builder /app/dashboard/dist ./dashboard/dist
ENV PORT=8000
EXPOSE $PORT
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
