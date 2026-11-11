from __future__ import annotations

import unittest

from fastapi import HTTPException

from tests._support import import_all_models, isolated_engine, session_factory

import_all_models()

from app.database import Base
from app.models.training import TrainingCourse, TrainingExam, WorkerTrainingRecord
from app.models.user import Worker
from app.services import training_service


class TrainingIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine)
        self.Session = session_factory(self.engine)
        self.db = self.Session()
        worker = Worker(openid="training-worker", nickname="培训师傅")
        course = TrainingCourse(
            title="安全培训",
            category="平台规则",
            credits=10,
            is_active=True,
        )
        self.db.add_all([worker, course])
        self.db.flush()
        self.worker_id = worker.id
        self.course_id = course.id
        for index in range(12):
            self.db.add(
                TrainingExam(
                    course_id=course.id,
                    question=f"题目 {index + 1}",
                    options=["A", "B", "C", "D"],
                    correct_answer="A",
                    sort_order=index,
                )
            )
        self.db.add(
            WorkerTrainingRecord(
                worker_id=worker.id,
                course_id=course.id,
                status="completed",
                exam_times=0,
                total_credits=0,
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_random_ten_are_graded_and_credits_awarded_only_once(self) -> None:
        questions = training_service.get_exam_questions(
            self.db, self.worker_id, self.course_id
        )
        self.assertEqual(len(questions), 10)
        answers = {str(question.id): "A" for question in questions}

        result = training_service.submit_exam(
            self.db, self.worker_id, self.course_id, answers
        )
        self.assertEqual(result["score"], 100)
        self.assertTrue(result["passed"])

        record = self.db.query(WorkerTrainingRecord).one()
        self.assertEqual(record.total_credits, 10)
        self.assertEqual(record.exam_times, 1)

        with self.assertRaises(HTTPException) as raised:
            training_service.submit_exam(
                self.db, self.worker_id, self.course_id, answers
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.db.refresh(record)
        self.assertEqual(record.total_credits, 10)
        self.assertEqual(record.exam_times, 1)

    def test_partial_answer_set_cannot_inflate_score(self) -> None:
        question = self.db.query(TrainingExam).first()
        with self.assertRaises(HTTPException) as raised:
            training_service.submit_exam(
                self.db,
                self.worker_id,
                self.course_id,
                {str(question.id): "A"},
            )
        self.assertEqual(raised.exception.status_code, 400)
        record = self.db.query(WorkerTrainingRecord).one()
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.exam_times, 0)
        self.assertEqual(record.total_credits, 0)


if __name__ == "__main__":
    unittest.main()
