from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse

from app.routers import auth, groups, students, assignments, submissions, submit


STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create initial teacher if needed
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models import Teacher
    from app.security import get_password_hash
    from app.config import settings
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Teacher).limit(1))
        if result.scalar_one_or_none() is None:
            teacher = Teacher(
                username=settings.first_teacher_username,
                hashed_password=get_password_hash(settings.first_teacher_password),
            )
            session.add(teacher)
            await session.commit()
    yield


app = FastAPI(title="Schrt", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(submissions.router, prefix="/api")
app.include_router(submit.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


if os.path.isdir(STATIC_DIR):
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        requested_path = os.path.normpath(os.path.join(STATIC_DIR, full_path))
        # Prevent path traversal outside static dir
        if not requested_path.startswith(os.path.normpath(STATIC_DIR)):
            return FileResponse(os.path.join(STATIC_DIR, "index.html"))
        if os.path.isfile(requested_path):
            return FileResponse(requested_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
