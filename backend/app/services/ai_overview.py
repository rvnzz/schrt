"""Агрегация состояния AI-проверки по всем заданиям преподавателя.

Функции чистые: получают уже загруженные объекты и возвращают словари, чтобы
логику можно было проверять без базы данных.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.ai_evidence import missing_evidence_hints

DONE = "done"
PENDING = "pending"
ERROR = "error"
DISABLED = "disabled"
# AI не нашёл обязательных материалов — решение отдаём человеку
MANUAL = "manual_review"

STALE_PENDING = "stale_pending"
NO_BRIEF = "no_brief"
NOT_QUEUED = "not_queued"
AI_OFF = "ai_off"

# Порядок важности для таблицы проблем: сначала то, что чинится одним кликом
KIND_ORDER = {
    ERROR: 0,
    MANUAL: 1,
    NO_BRIEF: 2,
    NOT_QUEUED: 3,
    STALE_PENDING: 4,
    AI_OFF: 5,
}

KIND_LABELS: Dict[str, str] = {
    ERROR: "Ошибка проверки",
    MANUAL: "Нужна ручная проверка",
    NO_BRIEF: "Нет текста задания",
    NOT_QUEUED: "Не поставлено в очередь",
    STALE_PENDING: "Давно в очереди",
    AI_OFF: "AI не настроен",
}

STATUS_KEYS = (DONE, PENDING, ERROR, DISABLED, MANUAL)
KIND_KEYS = (ERROR, MANUAL, STALE_PENDING, NO_BRIEF, NOT_QUEUED, AI_OFF)

LOW_GRADE = 3

# Строки `done`, в которых модель пожаловалась на недостающие материалы:
# их стоит перепроверить по новому промпту одной кнопкой
MISSING_EVIDENCE_SCAN_LIMIT = 300


def _reason(submission: Any) -> str:
    if submission.ai_error:
        return submission.ai_error
    if getattr(submission, "ai_review_reason", None):
        return submission.ai_review_reason
    # У строк до миграции причина аварии лежала в ai_feedback
    if (submission.ai_status or "") == ERROR and submission.ai_feedback:
        return submission.ai_feedback
    if (submission.ai_status or "") == DISABLED:
        return "Работа не была поставлена в очередь"
    return ""


def _age_seconds(now: datetime, value: Optional[datetime]) -> Optional[int]:
    if value is None:
        return None
    return max(0, int((now - value).total_seconds()))


def classify(
    submission: Any,
    *,
    ai_enabled: bool,
    has_brief: bool,
    now: datetime,
    stale_seconds: int,
) -> Optional[str]:
    """Вид проблемы или None, если проверка прошла либо идёт штатно."""
    status = submission.ai_status or DISABLED
    if status == DONE:
        return None
    # Работу уже увели к человеку: это проблема не про настройку AI
    if status == MANUAL:
        return MANUAL
    if not ai_enabled:
        return AI_OFF
    if status == ERROR:
        return ERROR
    if status == PENDING:
        age = _age_seconds(now, submission.ai_checked_at or submission.submitted_at)
        return STALE_PENDING if age is not None and age >= stale_seconds else None
    return NO_BRIEF if not has_brief else NOT_QUEUED


def _counter(keys) -> Dict[str, int]:
    return {key: 0 for key in keys}


def build_overview(
    assignments: List[Any],
    *,
    ai_enabled: bool,
    model: str = "",
    worker_poll_seconds: int = 5,
    stale_minutes: int = 15,
    now: Optional[datetime] = None,
    problem_limit: int = 200,
) -> Dict[str, Any]:
    now = now or datetime.utcnow()
    stale_seconds = max(60, stale_minutes * 60)

    totals = _counter(STATUS_KEYS)
    problems_by_kind = _counter(KIND_KEYS)
    assignment_rows: List[Dict[str, Any]] = []
    problems: List[Dict[str, Any]] = []
    low_grades: List[Dict[str, Any]] = []
    suspects: List[Dict[str, Any]] = []

    for assignment in assignments:
        has_brief = bool(assignment.brief_md)
        group_name = assignment.group.name if assignment.group else "—"
        status_counts = _counter(STATUS_KEYS)
        problem_counts = _counter(KIND_KEYS)
        grades = {str(grade): 0 for grade in range(2, 6)}
        grade_values: List[int] = []
        oldest_pending_seconds: Optional[int] = None
        last_checked_at: Optional[datetime] = None

        for submission in assignment.submissions or []:
            status = submission.ai_status or DISABLED
            if status in status_counts:
                status_counts[status] += 1
            if submission.ai_grade is not None:
                grade_values.append(submission.ai_grade)
                if str(submission.ai_grade) in grades:
                    grades[str(submission.ai_grade)] += 1
            if submission.ai_checked_at and (
                last_checked_at is None or submission.ai_checked_at > last_checked_at
            ):
                last_checked_at = submission.ai_checked_at
            if status == PENDING:
                age = _age_seconds(now, submission.submitted_at)
                if age is not None and (
                    oldest_pending_seconds is None or age > oldest_pending_seconds
                ):
                    oldest_pending_seconds = age

            kind = classify(
                submission,
                ai_enabled=ai_enabled,
                has_brief=has_brief,
                now=now,
                stale_seconds=stale_seconds,
            )
            if kind:
                problem_counts[kind] += 1
                problems.append(
                    {
                        "submission_id": submission.id,
                        "assignment_id": assignment.id,
                        "assignment_title": assignment.title,
                        "assignment_code": assignment.code,
                        "group_id": assignment.group_id,
                        "group_name": group_name,
                        "student": f"{submission.last_name} {submission.first_name}".strip(),
                        "original_filename": submission.original_filename,
                        "submitted_at": submission.submitted_at,
                        "status": status,
                        "kind": kind,
                        "kind_label": KIND_LABELS.get(kind, kind),
                        "reason": _reason(submission),
                        "attempts": submission.ai_attempts or 0,
                        "age_seconds": _age_seconds(now, submission.submitted_at),
                        "has_brief": has_brief,
                        # Чинится текстом задания: брифа просто нет
                        "fixable_by_brief": kind == NO_BRIEF,
                        # Можно вернуть в очередь прямо сейчас
                        "retryable": kind in (ERROR, NOT_QUEUED, MANUAL),
                        # Работу увели к человеку — подсказка, что именно не нашли
                        "manual_review": kind == MANUAL,
                    }
                )

            if submission.ai_grade is not None and submission.ai_grade <= LOW_GRADE:
                low_grades.append(
                    {
                        "submission_id": submission.id,
                        "assignment_id": assignment.id,
                        "assignment_title": assignment.title,
                        "group_name": group_name,
                        "student": f"{submission.last_name} {submission.first_name}".strip(),
                        "original_filename": submission.original_filename,
                        "grade": submission.ai_grade,
                        "feedback": submission.ai_feedback or "",
                        "submitted_at": submission.submitted_at,
                    }
                )

            # done-работа, где модель пожаловалась на недостающие материалы:
            # оценка опубликована по неполной работе, её стоит перепроверить
            if status == DONE:
                hints = missing_evidence_hints(submission.ai_feedback or "")
                if hints:
                    suspects.append(
                        {
                            "submission_id": submission.id,
                            "assignment_id": assignment.id,
                            "assignment_title": assignment.title,
                            "group_id": assignment.group_id,
                            "group_name": group_name,
                            "student": f"{submission.last_name} {submission.first_name}".strip(),
                            "original_filename": submission.original_filename,
                            "grade": submission.ai_grade,
                            "hint": hints[0],
                            "submitted_at": submission.submitted_at,
                        }
                    )

        for key, value in status_counts.items():
            totals[key] += value
        for key, value in problem_counts.items():
            problems_by_kind[key] += value

        assignment_rows.append(
            {
                "id": assignment.id,
                "title": assignment.title,
                "code": assignment.code,
                "group_id": assignment.group_id,
                "group_name": group_name,
                "deadline": assignment.deadline,
                "has_brief": has_brief,
                "brief_chars": len(assignment.brief_md or ""),
                "submissions_total": len(assignment.submissions or []),
                "status_counts": status_counts,
                "problem_counts": problem_counts,
                "problems_total": sum(problem_counts.values()),
                "avg_grade": round(sum(grade_values) / len(grade_values), 2) if grade_values else None,
                "grades": grades,
                "graded_total": len(grade_values),
                "oldest_pending_seconds": oldest_pending_seconds,
                "last_checked_at": last_checked_at,
            }
        )

    problems.sort(key=lambda row: (KIND_ORDER.get(row["kind"], 9), -(row["age_seconds"] or 0)))
    low_grades.sort(key=lambda row: (row["grade"], row["group_name"], row["student"]))
    suspects.sort(key=lambda row: (row["grade"] if row["grade"] is not None else 99, row["group_name"], row["student"]))

    return {
        "ai_enabled": ai_enabled,
        "model": model,
        "worker_poll_seconds": worker_poll_seconds,
        "stale_minutes": stale_minutes,
        "generated_at": now,
        "totals": {**totals, "submissions": sum(totals.values())},
        "problems_by_kind": problems_by_kind,
        "problems_total": len(problems),
        "assignments": sorted(assignment_rows, key=lambda row: (row["group_name"], row["title"])),
        "problems": problems[:problem_limit],
        "low_grades": low_grades,
        # Кандидаты на перепроверку: done-работы с жалобой на недостающие скриншоты
        "missing_evidence": {
            "count": len(suspects),
            "items": suspects[:MISSING_EVIDENCE_SCAN_LIMIT],
        },
    }
