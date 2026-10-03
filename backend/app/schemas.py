from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TeacherCreate(BaseModel):
    username: str
    password: str


class TeacherOut(BaseModel):
    id: int
    username: str
    model_config = ConfigDict(from_attributes=True)


class GroupCreate(BaseModel):
    name: str


class GroupOut(BaseModel):
    id: int
    name: str
    teacher_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StudentCreate(BaseModel):
    first_name: str
    last_name: str


class StudentOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    group_id: int
    model_config = ConfigDict(from_attributes=True)


class AssignmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    group_id: int
    deadline: Optional[datetime] = None
    is_hard_deadline: bool = False
    max_file_size_mb: int = 10
    allowed_extensions: Optional[List[str]] = None


class AssignmentOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    code: str
    group_id: int
    deadline: Optional[datetime]
    is_hard_deadline: bool
    max_file_size_mb: int
    allowed_extensions: Optional[List[str]]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AssignmentDetailOut(AssignmentOut):
    group: GroupOut
    submissions: List["SubmissionOut"] = []


class AssignmentWithSubmissionsOut(AssignmentOut):
    submissions: List["SubmissionOut"] = []


class GroupDetailOut(GroupOut):
    students: List["StudentOut"] = []
    assignments: List["AssignmentWithSubmissionsOut"] = []


class SubmissionOut(BaseModel):
    id: int
    assignment_id: int
    student_id: Optional[int]
    first_name: str
    last_name: str
    original_filename: str
    file_size: int
    submitted_at: datetime
    is_late: bool
    model_config = ConfigDict(from_attributes=True)


class SubmitInfo(BaseModel):
    title: str
    description: Optional[str]
    deadline: Optional[datetime]
    is_hard_deadline: bool
    max_file_size_mb: int
    allowed_extensions: Optional[List[str]]
    students: List[StudentOut]
    is_closed: bool


class SubmitPayload(BaseModel):
    first_name: str
    last_name: str


AssignmentWithSubmissionsOut.model_rebuild()
GroupDetailOut.model_rebuild()
AssignmentDetailOut.model_rebuild()
