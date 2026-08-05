"""培训考试 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_worker
from app.models.user import Worker
from app.schemas.training import (
    TrainingCourseResponse,
    ExamQuestionResponse,
    SubmitExamRequest,
    ExamResultResponse,
    WorkerTrainingRecordResponse,
    TrainingStatsResponse,
)
from app.services import training_service
from app.utils.response import success

router = APIRouter(prefix="/api/worker/training", tags=["培训考试"])


@router.get("/courses")
async def list_courses(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """培训课程列表"""
    items = training_service.list_courses(db, category)
    return success(data=[
        TrainingCourseResponse.model_validate(i).model_dump(mode="json")
        for i in items
    ])


@router.post("/courses/{course_id}/start")
async def start_course(
    course_id: int,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """开始学习课程"""
    record = training_service.start_course(db, worker.id, course_id)
    return success(data=WorkerTrainingRecordResponse.model_validate(record).model_dump(mode="json"))


@router.post("/courses/{course_id}/complete")
async def complete_course(
    course_id: int,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """完成课程学习"""
    record = training_service.complete_course(db, worker.id, course_id)
    return success(data=WorkerTrainingRecordResponse.model_validate(record).model_dump(mode="json"))


@router.get("/courses/{course_id}/exam")
async def get_exam_questions(
    course_id: int,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """获取考试题目（随机10道）"""
    questions = training_service.get_exam_questions(db, worker.id, course_id)
    return success(data=[
        ExamQuestionResponse.model_validate(q).model_dump(mode="json")
        for q in questions
    ])


@router.post("/courses/{course_id}/exam/submit")
async def submit_exam(
    course_id: int,
    req: SubmitExamRequest,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """提交考试"""
    result = training_service.submit_exam(db, worker.id, course_id, req.answers)
    return success(data=result)


@router.get("/records")
async def my_training_records(
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """我的学习记录"""
    from app.models.training import WorkerTrainingRecord
    items = db.query(WorkerTrainingRecord).filter(
        WorkerTrainingRecord.worker_id == worker.id
    ).order_by(WorkerTrainingRecord.created_at.desc()).limit(500).all()
    return success(data=[
        WorkerTrainingRecordResponse.model_validate(i).model_dump(mode="json")
        for i in items
    ])


@router.get("/stats")
async def training_stats(
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """培训统计"""
    stats = training_service.get_training_stats(db, worker.id)
    return success(data=stats)
