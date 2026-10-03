import io
import zipfile
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Submission
from app import s3


async def build_submissions_zip(submissions: List[Submission]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for submission in submissions:
            try:
                data = s3.get_object_bytes(submission.file_key)
                filename = f"{submission.last_name}_{submission.first_name}_{submission.id}_{submission.original_filename}"
                zf.writestr(filename, data)
            except Exception:
                continue
    buffer.seek(0)
    return buffer.read()
