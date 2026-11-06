import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Assignment, Group, Student, Submission
from app.schemas import SubmitInfo, SubmitParticipant, StudentOut, GroupMember
from app.config import settings
from app import s3

router = APIRouter(prefix="/submit", tags=["submit"])


def _parse_members(raw: Optional[str], model, detail: str) -> Optional[list]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("expected a list")
        return [model(**item) for item in data]
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _parse_group_members(raw: Optional[str]) -> Optional[List[GroupMember]]:
    return _parse_members(raw, GroupMember, "Invalid group_members format")


def _parse_participants(raw: Optional[str]) -> Optional[List[SubmitParticipant]]:
    return _parse_members(raw, SubmitParticipant, "Некорректный формат participants")


def _student_key(first_name: str, last_name: str) -> tuple:
    return (first_name.strip().lower(), last_name.strip().lower())


def _extension(filename: str) -> str:
    return filename.split(".")[-1].lower() if "." in filename else ""


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


@router.post("/{code}")
async def submit(
    code: str,
    first_name: str = Form(...),
    last_name: str = Form(...),
    is_group_work: bool = Form(False),
    group_members: Optional[str] = Form(None),
    participants: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Принимает работу.

    Каждый студент сдаёт отдельный файл: новые клиенты присылают `participants`
    и `files` (по файлу на участника). Старый формат с одним `file` и списком
    имён в `group_members` остаётся поддержанным.
    """
    legacy_members = _parse_group_members(group_members)
    parsed_participants = _parse_participants(participants)

    uploads = [
        upload
        for upload in ([file] if file is not None else []) + list(files or [])
        if upload is not None and upload.filename
    ]

    if parsed_participants:
        people = parsed_participants
    else:
        people = [SubmitParticipant(first_name=first_name, last_name=last_name)]

    if not uploads:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Прикрепите файл работы")

    if len(uploads) != len(people):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Нужен отдельный файл от каждого студента: "
                f"участников — {len(people)}, файлов — {len(uploads)}"
            ),
        )

    if len(people) > 1 and not is_group_work:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Несколько файлов можно сдать только вместе, отметив групповую работу",
        )

    keys = []
    for person in people:
        key = _student_key(person.first_name, person.last_name)
        if not key[0] or not key[1]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите имя и фамилию каждого студента",
            )
        if key in keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{person.first_name} {person.last_name} указан дважды — приложите по одному файлу от каждого",
            )
        keys.append(key)

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

    if not parsed_participants and is_group_work and not legacy_members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group work requires at least one member",
        )

    max_bytes = assignment.max_file_size_mb * 1024 * 1024
    allowed_extensions = (
        [a.lower() for a in assignment.allowed_extensions] if assignment.allowed_extensions else None
    )

    prepared = []
    for person, upload in zip(people, uploads):
        content = await upload.read()
        filename = upload.filename or "submission"
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Файл «{filename}» больше {assignment.max_file_size_mb} МБ",
            )
        if allowed_extensions and _extension(filename) not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Файл «{filename}» имеет недопустимый тип",
            )
        prepared.append((person, filename, content, upload.content_type or "application/octet-stream"))

    is_late = assignment.deadline is not None and now > assignment.deadline and not assignment.is_hard_deadline

    # Roster of the group to link submissions with students
    roster = {
        _student_key(student.first_name, student.last_name): student
        for student in assignment.group.students
    }

    ai_status = "pending" if (settings.ai_enabled and assignment.brief_md) else "disabled"
    ai_error = None
    if ai_status == "disabled":
        ai_error = (
            "AI-проверка не настроена (нет OPENCODE_GO_API_KEY)"
            if not settings.ai_enabled
            else "У задания нет текста для AI"
        )

    created = []
    auto_added: list[str] = []
    for index, (person, filename, content, content_type) in enumerate(prepared):
        key = _student_key(person.first_name, person.last_name)
        student = roster.get(key)

        if student is None:
            # Список группы пополняется сам: сдающий студент появляется в группе
            student = Student(
                first_name=person.first_name.strip(),
                last_name=person.last_name.strip(),
                group_id=assignment.group_id,
                is_auto_added=True,
            )
            assignment.group.students.append(student)
            db.add(student)
            await db.flush()
            roster[key] = student
            auto_added.append(f"{student.last_name} {student.first_name}")

        if parsed_participants:
            # Каждый участник получает свою работу, в списке участников — остальные
            members = [
                {
                    "first_name": other.first_name.strip(),
                    "last_name": other.last_name.strip(),
                }
                for other_index, other in enumerate(people)
                if other_index != index
            ]
            group_members_data = members if len(people) > 1 else None
        else:
            group_members_data = (
                [member.model_dump() for member in legacy_members] if legacy_members else None
            )

        object_key = s3.generate_file_key(assignment.code, filename)
        s3.upload_file(content, object_key, content_type)

        submission = Submission(
            assignment_id=assignment.id,
            student_id=student.id if student else None,
            first_name=person.first_name.strip(),
            last_name=person.last_name.strip(),
            file_key=object_key,
            original_filename=filename,
            file_size=len(content),
            submitted_at=now,
            is_late=is_late,
            is_group_work=is_group_work,
            group_members=group_members_data,
            ai_status=ai_status,
            ai_error=ai_error,
            ai_attempts=0,
        )
        db.add(submission)
        created.append(submission)

    await db.commit()
    for submission in created:
        await db.refresh(submission)

    return {
        "success": True,
        "count": len(created),
        "submitted_at": created[0].submitted_at,
        "is_late": is_late,
        "auto_added": auto_added,
    }
