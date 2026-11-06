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
    """XLSX с двумя листами: сдачи и оценки всех заданий группы."""
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
    errors_ws = wb.create_sheet("Ошибки AI")
    errors_ws.append(["Задание", "Фамилия", "Имя", "Файл", "Статус", "Попыток", "Причина"])
    for assignment, _ in per_assignment:
        for submission in assignment.submissions or []:
            if submission.ai_status not in ("error", "disabled") and not submission.ai_error:
                continue
            if submission.ai_status == "done":
                continue
            errors_ws.append(
                [
                    assignment.title,
                    submission.last_name,
                    submission.first_name,
                    submission.original_filename,
                    submission.ai_status,
                    submission.ai_attempts or 0,
                    submission.ai_error
                    or (submission.ai_feedback if submission.ai_status == "error" else "")
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
