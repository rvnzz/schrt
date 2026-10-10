import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import ValidationError
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Assignment, Group, Student, Submission
from app.schemas import SubmitInfo, SubmitPayload, StudentOut, GroupMember
from app.config import settings
from app import s3

router = APIRouter(prefix="/submit", tags=["submit"])


@router.get("/{code}", response_model=SubmitInfo)
async def get_submit_info(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Assignment)
        .where(Assignment.code == code)
        .options(selectinload(Assignment.group).selectinload(Group.students))
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    now = datetime.utcnow()
    is_closed = (
        assignment.deadline is not None
        and assignment.is_hard_deadline
        and now > assignment.deadline
    )

    return SubmitInfo(
        title=assignment.title,
        description=assignment.description,
        deadline=assignment.deadline,
        is_hard_deadline=assignment.is_hard_deadline,
        allow_group_submissions=assignment.allow_group_submissions,
        max_file_size_mb=assignment.max_file_size_mb,
        allowed_extensions=assignment.allowed_extensions,
        students=[StudentOut.model_validate(s) for s in assignment.group.students],
        is_closed=is_closed,
    )


def _parse_group_members(raw: Optional[str]) -> Optional[List[GroupMember]]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("group_members must be a list")
        return [GroupMember(**member) for member in data]
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group_members format",
        )


@router.post("/{code}")
async def submit(
    code: str,
    first_name: str = Form(...),
    last_name: str = Form(...),
    is_group_work: bool = Form(False),
    group_members: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    members = _parse_group_members(group_members)

    result = await db.execute(
        select(Assignment)
        .where(Assignment.code == code)
        .options(selectinload(Assignment.group).selectinload(Group.students))
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    now = datetime.utcnow()
    if assignment.deadline and assignment.is_hard_deadline and now > assignment.deadline:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Submission closed after deadline")

    if is_group_work and not assignment.allow_group_submissions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group submissions are not allowed for this assignment",
        )

    if is_group_work and (not members or len(members) == 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group work requires at least one member",
        )

    content = await file.read()
    max_bytes = assignment.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {assignment.max_file_size_mb} MB",
        )

    if assignment.allowed_extensions:
        ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        if ext not in [a.lower() for a in assignment.allowed_extensions]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File type not allowed")

    is_late = assignment.deadline is not None and now > assignment.deadline and not assignment.is_hard_deadline

    # Try to match primary student in group
    student_result = await db.execute(
        select(Student).where(
            and_(
                Student.group_id == assignment.group_id,
                Student.first_name.ilike(first_name.strip()),
                Student.last_name.ilike(last_name.strip()),
            )
        )
    )
    student = student_result.scalar_one_or_none()

    key = s3.generate_file_key(assignment.code, file.filename)
    s3.upload_file(content, key, file.content_type or "application/octet-stream")

    ai_status = "pending" if (settings.ai_enabled and assignment.brief_md) else "disabled"

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id if student else None,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        file_key=key,
        original_filename=file.filename,
        file_size=len(content),
        submitted_at=now,
        is_late=is_late,
        is_group_work=is_group_work,
        group_members=[member.model_dump() for member in members] if members else None,
        ai_status=ai_status,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    return {"success": True, "submitted_at": submission.submitted_at, "is_late": is_late}
