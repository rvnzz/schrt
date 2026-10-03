import csv
import io
from typing import List, Tuple


def parse_students_csv(content: bytes) -> Tuple[List[dict], List[str]]:
    """Parse CSV with columns first_name, last_name (or tries to detect order)."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV is empty or has no headers")

    headers = [h.strip().lower() for h in reader.fieldnames]
    candidates = {
        "first_name": ["first_name", "firstname", "name", "имя"],
        "last_name": ["last_name", "lastname", "surname", "фамилия"],
    }

    first_col = None
    last_col = None
    for header in headers:
        if header in candidates["first_name"]:
            first_col = header
        if header in candidates["last_name"]:
            last_col = header

    # Fallback: assume two columns [first_name, last_name]
    if first_col is None and last_col is None and len(headers) >= 2:
        first_col = headers[0]
        last_col = headers[1]

    if first_col is None or last_col is None:
        raise ValueError("CSV must contain first_name and last_name columns")

    students = []
    errors = []
    for idx, row in enumerate(reader, start=2):
        first = row.get(first_col, "").strip()
        last = row.get(last_col, "").strip()
        if not first or not last:
            errors.append(f"Row {idx}: missing name")
            continue
        students.append({"first_name": first, "last_name": last})

    return students, errors
