from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_teacher
from app.config import settings
from app.database import get_db
from app.models import Assignment, Group, Submission, Teacher
from app.services.ai_overview import KIND_LABELS, build_overview

router = APIRouter(prefix="/ai", tags=["ai"])

REQUEUE_STATUSES = ("disabled", "error")


class AIEnqueueRequest(BaseModel):
    assignment_id: Optional[int] = None
    submission_ids: Optional[List[int]] = None
    scope: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def _one_selector(self) -> "AIEnqueueRequest":
        chosen = [self.assignment_id is not None, bool(self.submission_ids), self.scope is not None]
        if sum(chosen) != 1:
            raise ValueError("Нужно указать один из параметров: assignment_id, submission_ids или scope")
        if self.scope not in (None, "all_errors"):
            raise ValueError("scope поддерживает только значение all_errors")
        return self


async def _teacher_assignments(teacher_id: int, db: AsyncSession) -> List[Assignment]:
    result = await db.execute(
        select(Assignment)
        .join(Group, Assignment.group_id == Group.id)
        .where(Group.teacher_id == teacher_id)
        .options(
            selectinload(Assignment.submissions),
            selectinload(Assignment.group),
        )
        .order_by(Assignment.created_at)
    )
    return list(result.scalars().all())


@router.get("/overview")
async def overview(
    group_id: Optional[int] = Query(default=None),
    kind: Optional[str] = Query(default=None, description="error | no_brief | not_queued | stale_pending | ai_off"),
    stale_minutes: int = Query(default=15, ge=1, le=1440),
    problem_limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Состояние AI-проверки по всем заданиям преподавателя."""
    if kind is not None and kind not in KIND_LABELS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неизвестный вид проблемы")

    assignments = await _teacher_assignments(current_teacher.id, db)
    if group_id is not None:
        assignments = [assignment for assignment in assignments if assignment.group_id == group_id]

    payload = build_overview(
        assignments,
        ai_enabled=settings.ai_enabled,
        model=settings.opencode_go_model,
        worker_poll_seconds=settings.worker_poll_seconds,
        stale_minutes=stale_minutes,
        problem_limit=problem_limit,
    )

    if kind is not None:
        payload["problems"] = [row for row in payload["problems"] if row["kind"] == kind]

    return payload


@router.post("/enqueue")
async def enqueue(
    data: AIEnqueueRequest,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Ставит непроверенные работы в очередь. Работы без текста задания пропускаются."""
    query = (
        select(Submission)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .join(Group, Assignment.group_id == Group.id)
        .where(
            Group.teacher_id == current_teacher.id,
            Submission.ai_status.in_(REQUEUE_STATUSES),
        )
        .options(selectinload(Submission.assignment))
        .order_by(Submission.submitted_at.asc())
    )

    if data.submission_ids:
        query = query.where(Submission.id.in_(data.submission_ids))
    elif data.assignment_id is not None:
        query = query.where(Assignment.id == data.assignment_id)
    elif data.scope == "all_errors":
        query = query.where(Submission.ai_status == "error")

    result = await db.execute(query)
    candidates = list(result.scalars().all())

    if data.assignment_id is not None:
        exists = await db.execute(
            select(Assignment.id)
            .join(Group, Assignment.group_id == Group.id)
            .where(Assignment.id == data.assignment_id, Group.teacher_id == current_teacher.id)
        )
        if exists.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    queueable: List[Submission] = []
    skipped_no_brief = 0
    for submission in candidates:
        if not submission.assignment.brief_md:
            skipped_no_brief += 1
            continue
        queueable.append(submission)

    selected = queueable[: data.limit]
    for submission in selected:
        submission.ai_status = "pending"
        submission.ai_grade = None
        submission.ai_feedback = None
        submission.ai_error = None

    await db.commit()

    return {
        "enqueued": len(selected),
        "skipped_no_brief": skipped_no_brief,
        "skipped_by_limit": max(0, len(queueable) - len(selected)),
    }
