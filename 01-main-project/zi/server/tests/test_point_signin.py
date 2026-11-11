from __future__ import annotations

import unittest

from fastapi import HTTPException

from tests._support import import_all_models, isolated_engine, session_factory

import_all_models()

from app.database import Base
from app.models.point import PointLog
from app.models.user import User
from app.services import point_service


class PointSigninTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = isolated_engine()
        Base.metadata.create_all(self.engine)
        self.Session = session_factory(self.engine)
        self.db = self.Session()
        self.user = User(openid="signin-user", nickname="签到用户")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_daily_signin_is_one_time_and_visible_in_balance(self) -> None:
        result = point_service.daily_signin(self.db, self.user)
        self.assertEqual(result["got_points"], 5)
        self.assertEqual(result["streak_days"], 1)

        summary = point_service.get_balance(self.db, self.user)
        self.assertEqual(summary["balance"], 5)
        self.assertTrue(summary["today_signin"])

        logs = point_service.list_logs(self.db, self.user)
        self.assertEqual(logs["items"][0]["reason"], "每日签到")

        with self.assertRaises(HTTPException):
            point_service.daily_signin(self.db, self.user)
        self.assertEqual(
            self.db.query(PointLog).filter(PointLog.user_id == self.user.id).count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
