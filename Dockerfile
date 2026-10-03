# syntax=docker/dockerfile:1

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Backend dependencies
FROM python:3.12-slim AS backend-builder

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Final image
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies if needed (asyncpg uses wheels, but keep libpq for safety)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

COPY backend/ ./
COPY --from=frontend-builder /app/frontend/dist ./static
COPY backend/entrypoint.sh ./entrypoint.sh

RUN chmod +x ./entrypoint.sh

EXPOSE 8000

ENV STATIC_DIR=/app/static

CMD ["./entrypoint.sh"]
