import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, ARRAY, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    groups = relationship("Group", back_populates="teacher", cascade="all, delete-orphan")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    teacher = relationship("Teacher", back_populates="groups")
    students = relationship("Student", back_populates="group", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="group", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("name", "teacher_id", name="uq_group_name_teacher"),)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    group = relationship("Group", back_populates="students")
    submissions = relationship("Submission", back_populates="student")

    __table_args__ = (UniqueConstraint("first_name", "last_name", "group_id", name="uq_student_name_group"),)


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    code = Column(String(4), unique=True, index=True, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    soft_deadline = Column(DateTime, nullable=True)
    hard_deadline = Column(DateTime, nullable=True)
    max_file_size_mb = Column(Integer, default=10)
    allowed_extensions = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    group = relationship("Group", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    file_key = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_late = Column(Boolean, default=False)

    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")
