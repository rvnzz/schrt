import csv
import io
import random
import string
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import StreamingResponse

from app.database import get_db
from app.auth import get_current_teacher
from app.models import Teacher, Group, Assignment, Submission
from app.schemas import AssignmentCreate, AssignmentUpdate, AssignmentOut, AssignmentDetailOut
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
        deadline=data.deadline,
        is_hard_deadline=data.is_hard_deadline,
        allow_group_submissions=data.allow_group_submissions,
        brief_md=data.brief_md,
        max_file_size_mb=data.max_file_size_mb,
        allowed_extensions=data.allowed_extensions,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.patch("/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Assignment)
        .join(Group)
        .where(Assignment.id == assignment_id, Group.teacher_id == current_teacher.id)
        .options(selectinload(Assignment.group))
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if data.group_id is not None and data.group_id != assignment.group_id:
        group_result = await db.execute(
            select(Group).where(Group.id == data.group_id, Group.teacher_id == current_teacher.id)
        )
        group = group_result.scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        assignment.group_id = group.id

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "group_id":
            continue
        if field == "title" and value is not None:
            value = value.strip()
        setattr(assignment, field, value)

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


@router.post("/{assignment_id}/grade-all", response_model=dict)
async def grade_all_submissions(
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
    if not assignment.brief_md:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment has no AI brief",
        )

    await db.execute(
        update(Submission)
        .where(
            Submission.assignment_id == assignment_id,
            Submission.ai_status.in_(["disabled", "error"]),
        )
        .values(ai_status="pending", ai_grade=None, ai_feedback=None)
    )
    await db.commit()
    return {"success": True}


@router.get("/{assignment_id}/grades-csv")
async def export_grades_csv(
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

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Фамилия",
        "Имя",
        "Файл",
        "Размер",
        "Время сдачи",
        "Просрочено",
        "Групповая",
        "Участники",
        "Статус AI",
        "Оценка AI",
        "Комментарий AI",
    ])

    for sub in assignment.submissions:
        members = ", ".join(
            f"{m.first_name} {m.last_name}" for m in (sub.group_members or [])
        )
        writer.writerow([
            sub.last_name,
            sub.first_name,
            sub.original_filename,
            sub.file_size,
            sub.submitted_at.isoformat() if sub.submitted_at else "",
            "Да" if sub.is_late else "Нет",
            "Да" if sub.is_group_work else "Нет",
            members,
            sub.ai_status,
            sub.ai_grade if sub.ai_grade is not None else "",
            sub.ai_feedback or "",
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="assignment_{assignment_id}_grades.csv"',
        },
    )


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
