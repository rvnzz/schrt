from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_teacher
from app.models import Teacher, Group, Student
from app.schemas import StudentOut
from app.services.csv_import import parse_students_csv

router = APIRouter(prefix="/groups/{group_id}/students", tags=["students"])


async def get_owned_group(group_id: int, teacher_id: int, db: AsyncSession) -> Group:
    result = await db.execute(select(Group).where(Group.id == group_id, Group.teacher_id == teacher_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


@router.get("", response_model=list[StudentOut])
async def list_students(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    await get_owned_group(group_id, current_teacher.id, db)
    result = await db.execute(select(Student).where(Student.group_id == group_id))
    return result.scalars().all()


@router.post("/import", response_model=list[StudentOut])
async def import_students(
    group_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    group = await get_owned_group(group_id, current_teacher.id, db)
    content = await file.read()
    try:
        parsed, errors = parse_students_csv(content)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    created = []
    for item in parsed:
        student = Student(first_name=item["first_name"], last_name=item["last_name"], group_id=group.id)
        db.add(student)
        created.append(student)

    try:
        await db.commit()
        for student in created:
            await db.refresh(student)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some students already exist")

    if errors:
        # Not failing import; report skipped rows
        pass

    return created


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    group_id: int,
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    await get_owned_group(group_id, current_teacher.id, db)
    result = await db.execute(select(Student).where(Student.id == student_id, Student.group_id == group_id))
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    await db.delete(student)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
