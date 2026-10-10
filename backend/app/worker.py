import asyncio
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Assignment, Submission
from app.services.ai_client import AIGradingError, grade_submission
from app.services.file_text import extract_file
from app.services.prompts import build_grading_prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def grade_one(session: AsyncSession, submission: Submission) -> None:
    assignment = submission.assignment
    if not assignment or not assignment.brief_md:
        submission.ai_status = "disabled"
        await session.commit()
        return

    submission.ai_status = "pending"
    await session.commit()

    try:
        logger.info("Grading submission %s (%s)", submission.id, submission.original_filename)
        extracted = extract_file(submission.file_key, submission.original_filename)

        author_name = f"{submission.first_name} {submission.last_name}"
        prompt_text = build_grading_prompt(
            assignment_title=assignment.title,
            brief_md=assignment.brief_md,
            author_name=author_name,
            is_group_work=submission.is_group_work,
            group_members=submission.group_members,
            extracted=extracted,
        )

        images = extracted.images_base64
        result = await grade_submission(prompt_text, images)

        submission.ai_grade = result["grade"]
        submission.ai_feedback = result["feedback"]
        submission.ai_status = "done"
        await session.commit()
        logger.info("Submission %s graded: %s", submission.id, result["grade"])
    except Exception as exc:
        logger.exception("Failed to grade submission %s", submission.id)
        submission.ai_status = "error"
        submission.ai_feedback = str(exc)[:500]
        await session.commit()


async def process_pending() -> int:
    graded = 0
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Submission)
            .where(Submission.ai_status == "pending")
            .options(selectinload(Submission.assignment))
            .order_by(Submission.submitted_at.asc())
            .limit(10)
        )
        submissions = result.scalars().all()

        for submission in submissions:
            await grade_one(session, submission)
            graded += 1

    return graded


async def run_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    if not settings.ai_enabled:
        logger.warning(
            "AI worker is not configured (OPENCODE_GO_API_KEY is empty). "
            "Set the key to enable automatic grading."
        )

    while stop_event is None or not stop_event.is_set():
        try:
            if settings.ai_enabled:
                graded = await process_pending()
                if graded:
                    logger.info("Graded %s submission(s)", graded)
        except Exception:
            logger.exception("Worker loop error")

        await asyncio.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped")
