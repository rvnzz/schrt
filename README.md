# Schrt — Сдача студенческих работ

Веб-приложение для преподавателей и студентов:
- преподаватель создаёт группы, импортирует студентов из CSV, создаёт задания с дедлайнами и получает уникальные ссылки для сдачи;
- студент переходит по ссылке, указывает имя/фамилию (с автоподстановкой из списка группы) и загружает файл;
- преподаватель просматривает сданные работы, выгружает их zip-архивом и скачивает отчёт по группе.

## Стек

- Backend: **FastAPI**, SQLAlchemy 2, Pydantic v2, Alembic, asyncpg
- Frontend: **Vue 3**, Vite, Pinia, Vue Router, **shadcn-vue**, **Tailwind CSS**
- База данных: **PostgreSQL**
- S3-хранилище: **MinIO** (elestio/minio) в Docker
- Инфраструктура: **Docker Compose**

## Быстрый старт

1. Скопируйте `.env.example` в `.env` и при необходимости измените значения:

```bash
cp .env.example .env
```

2. Запустите инфраструктуру и сервисы:

```bash
docker compose up --build
```

После запуска:
- Frontend: http://localhost:5174
- Backend API: http://localhost:8001
- MinIO Console: http://localhost:9001

3. Войдите под дефолтным преподавателем:
- Логин: `teacher`
- Пароль: `teacher`

## Локальная разработка (без Docker)

Если нужно запускать backend/frontend локально:

```bash
# Инфраструктура
docker compose up -d postgres minio createbuckets

# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8001

# Frontend (новое окно)
cd frontend
npm install
npm run dev -- --port 5174
```

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Подключение к PostgreSQL |
| `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | Подключение к MinIO |
| `SECRET_KEY` | JWT-секрет |
| `LINK_PREFIX` | Префикс ссылки для сдачи (например, `http://localhost:5174/s/`) |
| `FIRST_TEACHER_USERNAME`, `FIRST_TEACHER_PASSWORD` | Дефолтный преподаватель |
| `VITE_API_BASE_URL` | URL backend для frontend |

## Особенности

- Уникальная ссылка на задание генерируется автоматически из 4 символов `[a-z0-9]`.
- После **жёсткого дедлайна** загрузка файла блокируется.
- После **мягкого дедлайна** работа принимается, но помечается как просроченная.
- Размер файла ограничивается в настройках задания (по умолчанию 10 МБ).
- Импорт студентов поддерживает CSV с колонками `first_name` и `last_name` (или русскими вариантами `имя`, `фамилия`).
