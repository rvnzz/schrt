from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth import get_current_teacher
from app.models import Teacher, Group, Assignment
from app.schemas import GroupCreate, GroupOut, GroupDetailOut

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=list[GroupOut])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(select(Group).where(Group.teacher_id == current_teacher.id))
    return result.scalars().all()


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    group = Group(name=data.name.strip(), teacher_id=current_teacher.id)
    db.add(group)
    try:
        await db.commit()
        await db.refresh(group)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group with this name already exists")
    return group


@router.get("/{group_id}", response_model=GroupDetailOut)
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Group)
        .where(Group.id == group_id, Group.teacher_id == current_teacher.id)
        .options(selectinload(Group.students), selectinload(Group.assignments).selectinload(Assignment.submissions))
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(select(Group).where(Group.id == group_id, Group.teacher_id == current_teacher.id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    await db.delete(group)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
