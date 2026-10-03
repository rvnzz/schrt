from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Teacher
from app.schemas import Token, TeacherCreate, TeacherOut
from app.security import verify_password, create_access_token, get_password_hash
from app.auth import get_current_teacher
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


async def ensure_first_teacher(db: AsyncSession):
    result = await db.execute(select(Teacher).limit(1))
    if result.scalar_one_or_none() is None:
        teacher = Teacher(
            username=settings.first_teacher_username,
            hashed_password=get_password_hash(settings.first_teacher_password),
        )
        db.add(teacher)
        await db.commit()


@router.post("/login", response_model=Token)
async def login(form_data: TeacherCreate, db: AsyncSession = Depends(get_db)):
    await ensure_first_teacher(db)
    result = await db.execute(select(Teacher).where(Teacher.username == form_data.username))
    teacher = result.scalar_one_or_none()
    if teacher is None or not verify_password(form_data.password, teacher.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": teacher.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=TeacherOut)
async def me(current_teacher: Teacher = Depends(get_current_teacher)):
    return current_teacher
