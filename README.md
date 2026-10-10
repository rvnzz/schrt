# Schrt

Простая платформа для преподавателей и студентов: создание заданий, приём файлов, управление группами и AI-проверка сданных работ.

---

## Содержание

- [Возможности](#возможности)
- [Стек](#стек)
- [Быстрый старт](#быстрый-старт)
- [Production](#production)
- [AI-проверка работ](#ai-проверка-работ)
- [Переменные окружения](#переменные-окружения)
- [CI/CD](#cicd)
- [Архитектура](#архитектура)

---

## Возможности

### Для преподавателя

- Создание групп и импорт студентов из CSV.
- Создание заданий с дедлайном и опциональным **жёстким дедлайном**.
- Автоматическая генерация короткой ссылки на задание (`4 символа [a-z0-9]`).
- Просмотр сданных работ, скачивание отдельных файлов или всех сразу в ZIP.
- Экспорт отчёта по группе.
- AI-проверка сданных работ с оценкой по шкале 2–5 и развёрнутым комментарием.
- Ручной запуск AI-проверки со страницы задания: для всех работ сразу или для одной конкретной.
- Экспорт AI-оценок по заданию в CSV.

### Для студента

- Переход по короткой ссылке `/s/xxxx`.
- Автоподстановка имени и фамилии из списка группы.
- Загрузка файла перетаскиванием или через диалог выбора.
- Возможность групповой сдачи (если разрешено в задании).

---

## Стек

| Слой | Технологии |
|------|------------|
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, asyncpg |
| Frontend | Vue 3, Vite, Pinia, Vue Router, shadcn-vue, Tailwind CSS |
| База данных | PostgreSQL |
| S3-хранилище | MinIO (`elestio/minio`) |
| AI worker | отдельный контейнер `ai-grader` на том же образе |
| Контейнеризация | Docker Compose |

---

## Быстрый старт

Требования: установленные [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/).

```bash
# 1. Клонировать репозиторий
git clone https://github.com/rvnzz/schrt.git
cd schrt

# 2. Подготовить конфигурацию
cp .env.example .env

# 3. Запустить все сервисы
#    app      — FastAPI + собранный frontend
#    postgres — база данных
#    minio    — S3-хранилище файлов
#    ai-grader — фоновый воркер AI-проверки
docker compose up --build
```

После запуска:

- Приложение: http://localhost:8000
- REST API: http://localhost:8000/api
- MinIO Console: http://localhost:9001

Дефолтный преподаватель:

- Логин: `teacher`
- Пароль: `teacher`

> Порт приложения настраивается переменной `APP_PORT` в `.env` (по умолчанию `8000`).

---

## Production

Для production используется готовый образ из GitHub Container Registry.

```bash
cp .env.example .env
# Обязательно измените SECRET_KEY и FIRST_TEACHER_PASSWORD
# Добавьте OPENCODE_GO_API_KEY, если нужна AI-проверка

docker compose -f docker-compose.prod.yml up -d
```

По умолчанию скачивается образ `ghcr.io/rvnzz/schrt:main`. Чтобы использовать другой тег, задайте переменную `APP_IMAGE`:

```env
APP_IMAGE=ghcr.io/rvnzz/schrt:v1.0.0
```

### Важные production-настройки

- `SECRET_KEY` — смените на длинный случайный ключ.
- `FIRST_TEACHER_PASSWORD` — задайте надёжный пароль для первого преподавателя.
- `OPENCODE_GO_API_KEY` — добавьте ключ для включения AI-проверки.
- `LINK_PREFIX` — укажите публичный URL вашего приложения, например `https://schrt.example.com/s/`.

---

## AI-проверка работ

AI-проверка реализована через официальный API **opencode-go** (модель `glm-5.3-flash` по умолчанию).

### Как включить

Добавьте в `.env`:

```env
OPENCODE_GO_API_KEY=your_api_key
OPENCODE_GO_BASE_URL=https://opencode.ai/zen/go/v1
OPENCODE_GO_MODEL=glm-5.3-flash
WORKER_POLL_SECONDS=5
```

Без ключа воркер запускается, но проверка не выполняется — у сдачей будет статус `disabled`.

### Как это работает

1. Преподаватель в форме задания заполняет поле **«Текст задания для AI (markdown)»**. Этот текст видит только AI-агент.
2. После загрузки файла студентом фоновый воркер `ai-grader` извлекает:
   - текст из `txt`, `md`, `pdf`, `docx`, `xlsx`;
   - изображения из `docx`, `pdf` и графических файлов.
3. Агент получает задание, текст работы и изображения, затем возвращает оценку по шкале **2–5** и развёрнутый комментарий.
4. Результат отображается в таблице сданных работ. Длинный комментарий свёрнут по умолчанию и разворачивается по клику.
5. Преподаватель может вручную запустить повторную проверку:
   - **«Проверить все работы AI»** — для всех сдач со статусом `disabled` или `error`;
   - **«Перепроверить»** — для одной конкретной сдачи.
6. Есть экспорт всех AI-оценок по заданию в CSV (кнопка **«Экспорт оценок AI (CSV)»**).

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Подключение к PostgreSQL | `schrt` / `schrt_pass` / `schrt` |
| `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | Подключение к MinIO | `minio:9000` / `minioadmin` / `minioadmin` / `submissions` |
| `SECRET_KEY` | JWT-секрет для авторизации | `super-secret-key-change-in-production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни JWT-токена | `480` |
| `LINK_PREFIX` | Префикс ссылки для сдачи | `http://localhost:8000/s/` |
| `APP_PORT` | Внешний порт приложения | `8000` |
| `APP_IMAGE` | Docker-образ для production | `ghcr.io/rvnzz/schrt:main` |
| `FIRST_TEACHER_USERNAME`, `FIRST_TEACHER_PASSWORD` | Дефолтный преподаватель | `teacher` / `teacher` |
| `OPENCODE_GO_API_KEY` | Ключ opencode-go для AI-проверки | — |
| `OPENCODE_GO_BASE_URL` | Базовый URL opencode-go API | `https://opencode.ai/zen/go/v1` |
| `OPENCODE_GO_MODEL` | Модель для оценки | `glm-5.3-flash` |
| `WORKER_POLL_SECONDS` | Интервал опроса БД воркером | `5` |

---

## CI/CD

В `.github/workflows/build.yml` настроен GitHub Actions workflow, который:

- запускается при пуше в `main`/`master` и при создании тегов `v*`;
- собирает production Docker-образ;
- публикует его в **GitHub Container Registry**: `ghcr.io/rvnzz/schrt`.

> Сборка выполняется только для платформы `linux/amd64`.

---

## Архитектура

Приложение собирается в **один production Docker-образ**:

1. **Frontend-builder stage** — собирает Vue-приложение (`npm run build`).
2. **Backend stage** — копирует Python-зависимости и код FastAPI.
3. **Final stage** — объединяет backend и статику frontend в одном контейнере.

FastAPI раздаёт собранную статику по корневому URL, а API доступно по префиксу `/api`. Это позволяет развёртывать приложение как единый сервис без отдельного nginx для фронтенда.

Отдельный контейнер `ai-grader` использует тот же образ, но запускает фоновый воркер (`python -m app.worker`), который асинхронно проверяет сдачи из очереди в PostgreSQL.

