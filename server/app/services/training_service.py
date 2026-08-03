"""培训考试业务逻辑"""

import random
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.training import TrainingCourse, TrainingExam, WorkerTrainingRecord


def list_courses(db: Session, category: str = None) -> List[TrainingCourse]:
    """课程列表"""
    q = db.query(TrainingCourse).filter(TrainingCourse.is_active == True)
    if category:
        q = q.filter(TrainingCourse.category == category)
    return q.order_by(TrainingCourse.sort_order.asc()).all()


def start_course(db: Session, worker_id: int, course_id: int) -> WorkerTrainingRecord:
    """开始学习课程"""
    course = db.query(TrainingCourse).filter(
        TrainingCourse.id == course_id,
        TrainingCourse.is_active.is_(True),
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在或已下架")
    record = db.query(WorkerTrainingRecord).filter(
        WorkerTrainingRecord.worker_id == worker_id,
        WorkerTrainingRecord.course_id == course_id,
    ).first()
    if not record:
        record = WorkerTrainingRecord(
            worker_id=worker_id,
            course_id=course_id,
            status="studying",
            started_at=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def complete_course(db: Session, worker_id: int, course_id: int) -> WorkerTrainingRecord:
    """完成课程学习"""
    record = db.query(WorkerTrainingRecord).filter(
        WorkerTrainingRecord.worker_id == worker_id,
        WorkerTrainingRecord.course_id == course_id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="学习记录不存在")
    if record.status in ("completed", "passed", "failed"):
        return record

    record.status = "completed"
    record.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def get_exam_questions(db: Session, worker_id: int, course_id: int) -> List[TrainingExam]:
    """获取考试题目（随机抽取10道）"""
    record = db.query(WorkerTrainingRecord).filter(
        WorkerTrainingRecord.worker_id == worker_id,
        WorkerTrainingRecord.course_id == course_id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="学习记录不存在")
    if record.status == "studying":
        raise HTTPException(status_code=409, detail="请先完成课程学习再参加考试")
    questions = db.query(TrainingExam).filter(TrainingExam.course_id == course_id).all()
    if not questions:
        raise HTTPException(status_code=404, detail="该课程暂无考题")
    if len(questions) <= 10:
        return questions
    return random.sample(questions, 10)


def submit_exam(db: Session, worker_id: int, course_id: int, answers: dict) -> dict:
    """提交考试"""
    record = db.query(WorkerTrainingRecord).filter(
        WorkerTrainingRecord.worker_id == worker_id,
        WorkerTrainingRecord.course_id == course_id,
    ).with_for_update().first()
    if not record:
        raise HTTPException(status_code=404, detail="学习记录不存在")
    if record.status == "studying":
        raise HTTPException(status_code=409, detail="请先完成课程学习再参加考试")
    if record.status == "passed":
        raise HTTPException(status_code=409, detail="该课程考试已通过，无需重复提交")

    question_ids = [int(question_id) for question_id in answers]
    course_question_count = db.query(TrainingExam).filter(
        TrainingExam.course_id == course_id
    ).count()
    if course_question_count == 0:
        raise HTTPException(status_code=404, detail="该课程暂无考题")
    expected_count = min(10, course_question_count)
    if len(question_ids) != expected_count:
        raise HTTPException(status_code=400, detail=f"本次考试必须提交 {expected_count} 道答案")
    questions = db.query(TrainingExam).filter(
        TrainingExam.course_id == course_id,
        TrainingExam.id.in_(question_ids),
    ).all()
    if len(questions) != len(question_ids):
        raise HTTPException(status_code=400, detail="答案中包含不属于本课程的题目")

    correct = 0
    correct_answers = {}
    for q in questions:
        user_ans = answers.get(str(q.id), "")
        if user_ans.upper() == q.correct_answer.upper():
            correct += 1
        correct_answers[str(q.id)] = q.correct_answer.upper()

    score = int(correct / len(questions) * 100)
    passed = score >= 80

    record.exam_score = score
    record.exam_times = (record.exam_times or 0) + 1
    if passed:
        record.status = "passed"
        course = db.query(TrainingCourse).filter(TrainingCourse.id == course_id).first()
        if course:
            record.total_credits = max(record.total_credits or 0, course.credits or 0)
    else:
        record.status = "failed"

    db.commit()
    db.refresh(record)
    return {
        "score": score,
        "passed": passed,
        "correct_answers": correct_answers,
        "total_questions": len(questions),
    }


def get_training_stats(db: Session, worker_id: int) -> dict:
    """师傅培训统计"""
    records = db.query(WorkerTrainingRecord).filter(WorkerTrainingRecord.worker_id == worker_id).all()
    total_credits = sum(r.total_credits for r in records)
    completed = sum(1 for r in records if r.status in ("completed", "passed", "failed"))
    passed = sum(1 for r in records if r.status == "passed")
    total_exam_times = sum(r.exam_times for r in records)
    pass_rate = passed / total_exam_times * 100 if total_exam_times > 0 else 0
    return {
        "total_credits": total_credits,
        "completed_courses": completed,
        "passed_exams": passed,
        "total_exam_times": total_exam_times,
        "exam_pass_rate": round(pass_rate, 2),
    }
