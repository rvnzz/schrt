import csv
import io
from datetime import datetime
from typing import Dict, List, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.models import Assignment, Submission

SUBMITTED = "✅"
LATE = "⚠️"
MISSING = "❌"


def _submitted_at(submission: Submission) -> datetime:
    return submission.submitted_at or datetime.min


def _latest_by_student(assignment: Assignment) -> Dict[int, Submission]:
    """Связка student_id -> последняя сдача по заданию."""
    latest: Dict[int, Submission] = {}
    for submission in assignment.submissions or []:
        if not submission.student_id:
            continue
        current = latest.get(submission.student_id)
        if current is None or _submitted_at(submission) >= _submitted_at(current):
            latest[submission.student_id] = submission
    return latest


def build_group_report(
    group_name: str, students: List["object"], assignments: List[Assignment]
) -> bytes:
    """XLSX с тремя листами: сдачи, оценки всех заданий группы и проблемы AI-проверки."""
    # Pre-compute lookups once instead of per student
    per_assignment: List[Tuple[Assignment, Dict[int, Submission]]] = [
        (assignment, _latest_by_student(assignment)) for assignment in assignments
    ]

    wb = Workbook()

    # --- Лист 1: сдачи ---
    ws = wb.active
    ws.title = "Сдачи"
    ws.append(["Фамилия", "Имя"] + [assignment.title for assignment, _ in per_assignment] + ["Сдано"])
    for student in students:
        row = [student.last_name, student.first_name]
        submitted_count = 0
        for _, latest in per_assignment:
            submission = latest.get(student.id)
            if submission is None:
                row.append(MISSING)
            elif submission.is_late:
                row.append(LATE)
                submitted_count += 1
            else:
                row.append(SUBMITTED)
                submitted_count += 1
        row.append(f"{submitted_count} из {len(per_assignment)}")
        ws.append(row)

    _style_sheet(ws, bold_first_row=True)

    # --- Лист 2: оценки ---
    grades_ws = wb.create_sheet("Оценки")
    grades_ws.append(
        ["Фамилия", "Имя"]
        + [assignment.title for assignment, _ in per_assignment]
        + ["Средний балл", "Оценок", "Без оценки"]
    )
    for student in students:
        row: List = [student.last_name, student.first_name]
        grades: List[int] = []
        missing = 0
        for assignment, latest in per_assignment:
            submission = latest.get(student.id)
            grade = submission.ai_grade if submission is not None else None
            if grade is None:
                row.append("-")
                if submission is None:
                    missing += 1
            else:
                row.append(grade)
                grades.append(grade)
        average = round(sum(grades) / len(grades), 2) if grades else ""
        row.extend([average, len(grades), missing])
        grades_ws.append(row)

    _style_sheet(grades_ws, bold_first_row=True)

    # --- Лист 3: проблемы AI-проверки ---
    errors_ws = wb.create_sheet("Проблемы AI")
    errors_ws.append(["Задание", "Фамилия", "Имя", "Файл", "Статус", "Попыток", "Причина"])
    for assignment, _ in per_assignment:
        for submission in assignment.submissions or []:
            status = submission.ai_status or "disabled"
            # done и pending — штатные состояния, человек их ищут в других листах
            if status in ("done", "pending"):
                continue
            errors_ws.append(
                [
                    assignment.title,
                    submission.last_name,
                    submission.first_name,
                    submission.original_filename,
                    status,
                    submission.ai_attempts or 0,
                    submission.ai_review_reason
                    or submission.ai_error
                    or (submission.ai_feedback if status == "error" else "")
                    or "",
                ]
            )
    if errors_ws.max_row == 1:
        errors_ws.append(["Проблем AI-проверки нет"] + [""] * 6)
    _style_sheet(errors_ws, bold_first_row=True)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read()


def build_group_grades_csv(
    group_name: str, students: List["object"], assignments: List[Assignment]
) -> bytes:
    """Тот же срез оценок, но в CSV для загрузки в таблицу/Журнал."""
    per_assignment: List[Tuple[Assignment, Dict[int, Submission]]] = [
        (assignment, _latest_by_student(assignment)) for assignment in assignments
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([f"Группа: {group_name}"])
    writer.writerow(
        ["Фамилия", "Имя"]
        + [assignment.title for assignment, _ in per_assignment]
        + ["Средний балл", "Оценок", "Без оценки"]
    )

    for student in students:
        row: List = [student.last_name, student.first_name]
        grades: List[int] = []
        missing = 0
        for assignment, latest in per_assignment:
            submission = latest.get(student.id)
            grade = submission.ai_grade if submission is not None else None
            if grade is None:
                row.append("")
                if submission is None:
                    missing += 1
            else:
                row.append(grade)
                grades.append(grade)
        row.extend(
            [
                round(sum(grades) / len(grades), 2) if grades else "",
                len(grades),
                missing,
            ]
        )
        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")


def build_group_submitters_xlsx(
    group_name: str, assignments: List[Assignment]
) -> bytes:
    """XLSX «кто сдавал»: по каждому заданию — список сдавших студентов.

    Лист 1 «Сдавшие»: строка на каждую сдачу (последняя сдача студента по заданию).
    Лист 2 «Сводка»: сколько человек сдало каждое задание.
    """
    wb = Workbook()

    # --- Лист 1: сдавшие ---
    ws = wb.active
    ws.title = "Сдавшие"
    ws.append(
        ["Задание", "Фамилия", "Имя", "Вместе с", "Файл", "Дата сдачи", "Вовремя", "Оценка"]
    )

    for assignment in assignments:
        latest = _latest_by_student(assignment)
        # Сдачи без привязки к студенту (анонимные) — тоже сдавшие, идём отдельными строками
        anonymous = [s for s in assignment.submissions or [] if not s.student_id]
        rows: List[Submission] = list(latest.values()) + anonymous
        rows.sort(key=lambda s: (s.last_name or "", s.first_name or ""))

        for submission in rows:
            members = ""
            if submission.is_group_work and submission.group_members:
                members = ", ".join(
                    f"{m.get('last_name', '')} {m.get('first_name', '')}".strip()
                    for m in submission.group_members
                )
            submitted_at = submission.submitted_at
            grade = submission.ai_grade
            ws.append(
                [
                    assignment.title,
                    submission.last_name,
                    submission.first_name,
                    members,
                    submission.original_filename or "",
                    submitted_at.strftime("%d.%m.%Y %H:%M") if submitted_at else "",
                    "да" if not submission.is_late else "нет",
                    grade if grade is not None else "",
                ]
            )

    if ws.max_row == 1:
        ws.append(["Сдач пока нет"] + [""] * 7)
    _style_sheet(ws, bold_first_row=True)

    # --- Лист 2: сводка по заданиям ---
    summary_ws = wb.create_sheet("Сводка")
    summary_ws.append(["Задание", "Сдало человек", "Всего сдач"])
    for assignment in assignments:
        submissions = assignment.submissions or []
        unique = len(_latest_by_student(assignment)) + len(
            [s for s in submissions if not s.student_id]
        )
        summary_ws.append([assignment.title, unique, len(submissions)])
    if summary_ws.max_row == 1:
        summary_ws.append(["Заданий пока нет"] + [""] * 2)
    _style_sheet(summary_ws, bold_first_row=True)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read()


def _style_sheet(ws, bold_first_row: bool) -> None:
    if bold_first_row:
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(wrap_text=True, vertical="center")

    ws.freeze_panes = "C2"
    for column_index in range(1, ws.max_column + 1):
        letter = get_column_letter(column_index)
        if column_index <= 2:
            ws.column_dimensions[letter].width = 18
        else:
            ws.column_dimensions[letter].width = 22
