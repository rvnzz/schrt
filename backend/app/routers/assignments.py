import random
import string
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth import get_current_teacher
from app.models import Teacher, Group, Assignment, Submission
from app.schemas import AssignmentCreate, AssignmentOut, AssignmentDetailOut
from app.config import settings

router = APIRouter(prefix="/assignments", tags=["assignments"])


def generate_code(length: int = 4) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


async def unique_code(db: AsyncSession) -> str:
    while True:
        code = generate_code()
        result = await db.execute(select(Assignment).where(Assignment.code == code))
        if result.scalar_one_or_none() is None:
            return code


@router.get("", response_model=list[AssignmentOut])
async def list_assignments(
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Assignment)
        .join(Group)
        .where(Group.teacher_id == current_teacher.id)
        .order_by(Assignment.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    data: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    group_result = await db.execute(select(Group).where(Group.id == data.group_id, Group.teacher_id == current_teacher.id))
    group = group_result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    code = await unique_code(db)
    assignment = Assignment(
        title=data.title.strip(),
        description=data.description,
        code=code,
        group_id=group.id,
        soft_deadline=data.soft_deadline,
        hard_deadline=data.hard_deadline,
        max_file_size_mb=data.max_file_size_mb,
        allowed_extensions=data.allowed_extensions,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.get("/{assignment_id}", response_model=AssignmentDetailOut)
async def get_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Assignment)
        .join(Group)
        .where(Assignment.id == assignment_id, Group.teacher_id == current_teacher.id)
        .options(selectinload(Assignment.submissions), selectinload(Assignment.group))
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Assignment)
        .join(Group)
        .where(Assignment.id == assignment_id, Group.teacher_id == current_teacher.id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    await db.delete(assignment)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{assignment_id}/link")
async def get_assignment_link(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Assignment)
        .join(Group)
        .where(Assignment.id == assignment_id, Group.teacher_id == current_teacher.id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return {"link": f"{settings.link_prefix}{assignment.code}"}
