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

## Быстрый старт (разработка / сборка из исходников)

1. Скопируйте `.env.example` в `.env` и при необходимости измените значения:

```bash
cp .env.example .env
```

2. Запустите всё одной командой:

```bash
docker compose up --build
```

После запуска приложение доступно по адресу:
- **http://localhost:8000** — единый endpoint (frontend + API)
- **http://localhost:8000/api** — REST API
- **http://localhost:9001** — MinIO Console

3. Войдите под дефолтным преподавателем:
- Логин: `teacher`
- Пароль: `teacher`

## Запуск из готового образа (production)

Если образ уже опубликован в `ghcr.io/rvnzz/schrt`, используйте `docker-compose.prod.yml`:

```bash
cp .env.example .env
# отредактируйте .env: установите SECRET_KEY, FIRST_TEACHER_PASSWORD и другие параметры
docker compose -f docker-compose.prod.yml up -d
```

По умолчанию скачивается образ с тегом `main` (`ghcr.io/rvnzz/schrt:main`). Чтобы использовать другой тег, задайте переменную `APP_IMAGE` в `.env`:

```env
APP_IMAGE=ghcr.io/rvnzz/schrt:v1.0.0
```

Образ будет скачан из GitHub Container Registry, сборка не требуется.

## Архитектура образа

В продакшене frontend и backend собираются в **один Docker-образ**:
- мультистейдж-сборка: сначала собирается frontend (`npm run build`), затем backend;
- готовый образ содержит FastAPI, который раздаёт собранную статику Vue по корневому URL;
- API доступно по префиксу `/api`.

## GitHub Actions

В `.github/workflows/build.yml` настроен workflow, который:
- собирает Docker-образ при пуше в `main`/`master` и при создании тегов `v*`;
- публикует образ в **GitHub Container Registry (ghcr.io)**;
- поддерживает multi-platform сборку (`linux/amd64`, `linux/arm64`).

Для публикации убедитесь, что в репозитории включены **Actions permissions** → `Read and write permissions`, и разрешён пакет `ghcr.io`.

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Подключение к PostgreSQL |
| `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | Подключение к MinIO |
| `SECRET_KEY` | JWT-секрет |
| `LINK_PREFIX` | Префикс ссылки для сдачи (например, `http://localhost:8000/s/`) |
| `APP_PORT` | Внешний порт приложения (по умолчанию `8000`) |
| `FIRST_TEACHER_USERNAME`, `FIRST_TEACHER_PASSWORD` | Дефолтный преподаватель |

## Особенности

- Уникальная ссылка на задание генерируется автоматически из 4 символов `[a-z0-9]`.
- После **жёсткого дедлайна** загрузка файла блокируется.
- После **мягкого дедлайна** работа принимается, но помечается как просроченная.
- Размер файла ограничивается в настройках задания (по умолчанию 10 МБ).
- Импорт студентов поддерживает CSV с колонками `first_name` и `last_name` (или русскими вариантами `имя`, `фамилия`).
