from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Teacher
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_teacher(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Teacher:
    payload = decode_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    username = payload["sub"]
    result = await db.execute(select(Teacher).where(Teacher.username == username))
    teacher = result.scalar_one_or_none()
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return teacher
