from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Date,
    Text,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from db.core import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)

    grade = Column(String)
    subjects = relationship("Subject", back_populates="user", cascade="all, delete")
    schedule = relationship("Schedule", back_populates="user", cascade="all, delete")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    classroom = Column(String(50))

    user = relationship("User", back_populates="subjects")
    lessons = relationship("Schedule", back_populates="subject")

    load_level = Column(Integer)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_subject_name"),
    )


class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    lesson_number = Column(Integer, nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"))

    user = relationship("User", back_populates="schedule")
    subject = relationship("Subject", back_populates="lessons")
    homework = relationship("Homework", back_populates="schedule", cascade="all, delete")

    __table_args__ = (
        UniqueConstraint("user_id", "date", "lesson_number",
                         name="uq_user_day_lesson"),
    )


class Homework(Base):
    __tablename__ = "homework"

    id = Column(Integer, primary_key=True)
    schedule_id = Column(
        Integer,
        ForeignKey("schedule.id", ondelete="CASCADE"),
        nullable=False
    )

    text = Column(Text, nullable=True)

    schedule = relationship("Schedule", back_populates="homework")