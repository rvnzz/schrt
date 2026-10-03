import io
from typing import List
from openpyxl import Workbook
from openpyxl.styles import Font

from app.models import Assignment, Student


def build_group_report(group_name: str, students: List[Student], assignments: List[Assignment]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"

    headers = ["Фамилия", "Имя"] + [a.title for a in assignments]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Build lookup: (student_id, assignment_id) -> submitted
    submission_lookup = {}
    for assignment in assignments:
        for sub in assignment.submissions:
            if sub.student_id:
                submission_lookup[(sub.student_id, assignment.id)] = "✅" if not sub.is_late else "⚠️"

    for student in students:
        row = [student.last_name, student.first_name]
        for assignment in assignments:
            row.append(submission_lookup.get((student.id, assignment.id), "❌"))
        ws.append(row)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read()
