from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, groups, students, assignments, submissions, submit


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
