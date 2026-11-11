"""师傅培训与技能考试"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, JSON
from app.database import Base


class TrainingCourse(Base):
    """培训课程"""
    __tablename__ = "training_courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, comment="平台规则/服务礼仪/水电安全/家电维修")
    content = Column(Text, comment="课程内容（Markdown）")
    video_url = Column(String(500), nullable=True)
    duration_minutes = Column(Integer, default=15, comment="课程时长")
    credits = Column(Integer, default=10, comment="学分")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrainingExam(Base):
    """考试题库"""
    __tablename__ = "training_exams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("training_courses.id"), nullable=False)

    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False, comment="[A, B, C, D]")
    correct_answer = Column(String(10), nullable=False, comment="A/B/C/D")
    sort_order = Column(Integer, default=0)


class WorkerTrainingRecord(Base):
    """师傅学习记录"""
    __tablename__ = "worker_training_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("training_courses.id"), nullable=False)

    status = Column(String(20), default="studying", comment="studying/completed/passed/failed")
    exam_score = Column(Integer, nullable=True, comment="考试分数")
    exam_times = Column(Integer, default=0, comment="考试次数")
    total_credits = Column(Integer, default=0, comment="累计学分")

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
