from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import StreamingResponse

from app.database import get_db
from app.auth import get_current_teacher
from app.models import Teacher, Group, Assignment, Submission
from app.services.zip_export import build_submissions_zip
from app.services.report_export import build_group_report
from app import s3

router = APIRouter(prefix="/submissions", tags=["submissions"])


async def get_owned_assignment(assignment_id: int, teacher_id: int, db: AsyncSession) -> Assignment:
    result = await db.execute(
        select(Assignment)
        .join(Group, Assignment.group_id == Group.id)
        .where(Assignment.id == assignment_id, Group.teacher_id == teacher_id)
        .options(selectinload(Assignment.submissions))
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


@router.get("/{submission_id}/download")
async def download_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Submission)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .join(Group, Assignment.group_id == Group.id)
        .where(Submission.id == submission_id, Group.teacher_id == current_teacher.id)
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    s3_response = s3.get_object_stream(submission.file_key)

    def streamer():
        body = s3_response["Body"]
        for chunk in body.iter_chunks(chunk_size=1024 * 1024):
            yield chunk

    return StreamingResponse(
        streamer(),
        media_type=s3_response.get("ContentType", "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{submission.original_filename}"',
        },
    )


@router.post("/{submission_id}/grade", response_model=dict)
async def grade_submission_manual(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    result = await db.execute(
        select(Submission)
        .join(Assignment)
        .join(Group)
        .where(Submission.id == submission_id, Group.teacher_id == current_teacher.id)
        .options(selectinload(Submission.assignment))
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if not submission.assignment.brief_md:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment has no AI brief",
        )

    submission.ai_status = "pending"
    submission.ai_grade = None
    submission.ai_feedback = None
    await db.commit()
    return {"success": True}


@router.get("/assignments/{assignment_id}/download-all")
async def download_all(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    assignment = await get_owned_assignment(assignment_id, current_teacher.id, db)
    if not assignment.submissions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No submissions yet")
    zip_bytes = await build_submissions_zip(assignment.submissions)
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=assignment_{assignment_id}_submissions.zip"},
    )


@router.get("/groups/{group_id}/report")
async def group_report(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    group_result = await db.execute(
        select(Group)
        .where(Group.id == group_id, Group.teacher_id == current_teacher.id)
        .options(selectinload(Group.students))
    )
    group = group_result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    result = await db.execute(
        select(Assignment)
        .where(Assignment.group_id == group_id)
        .options(selectinload(Assignment.submissions))
    )
    assignments = result.scalars().all()
    report_bytes = build_group_report(group.name, group.students, assignments)
    return StreamingResponse(
        iter([report_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=group_{group_id}_report.xlsx"},
    )
