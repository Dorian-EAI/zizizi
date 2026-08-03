"""培训考试 Pydantic 模型"""

from datetime import datetime
from typing import Dict, Literal, Optional, List
from pydantic import BaseModel, Field, field_validator


class TrainingCourseResponse(BaseModel):
    id: int
    title: str
    category: str
    content: Optional[str]
    video_url: Optional[str]
    duration_minutes: int
    credits: int
    sort_order: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ExamQuestionResponse(BaseModel):
    id: int
    course_id: int
    question: str
    options: List[str]
    sort_order: int

    class Config:
        from_attributes = True


class SubmitExamRequest(BaseModel):
    answers: Dict[str, Literal["A", "B", "C", "D"]] = Field(
        ..., min_length=1, max_length=10
    )

    @field_validator("answers", mode="before")
    @classmethod
    def normalize_answers(cls, value):
        if not isinstance(value, dict):
            raise ValueError("answers 必须为题目 ID 到选项的映射")
        normalized = {}
        for raw_id, raw_answer in value.items():
            question_id = str(raw_id).strip()
            if not question_id.isdigit() or int(question_id) <= 0:
                raise ValueError("题目 ID 无效")
            normalized[question_id] = str(raw_answer).strip().upper()
        return normalized

    model_config = {"extra": "forbid"}


class ExamResultResponse(BaseModel):
    score: int
    passed: bool
    correct_answers: Dict[str, str]
    total_questions: int


class WorkerTrainingRecordResponse(BaseModel):
    id: int
    worker_id: int
    course_id: int
    status: str
    exam_score: Optional[int]
    exam_times: int
    total_credits: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    course: Optional[TrainingCourseResponse] = None

    class Config:
        from_attributes = True


class TrainingStatsResponse(BaseModel):
    total_credits: int
    completed_courses: int
    passed_exams: int
    total_exam_times: int
    exam_pass_rate: float
