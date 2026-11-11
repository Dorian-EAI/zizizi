#!/usr/bin/env python3
"""一次性创建生产首个超级管理员。

仅当 admins 表完全为空时执行；密码从隐藏终端输入或标准输入读取，绝不打印。
隐藏输入的密码被视为最终密码；后续 API 创建/重置的管理员仍必须首次改密。
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.admin import Admin  # noqa: E402
from app.utils.security import hash_password  # noqa: E402
from sqlalchemy import text  # noqa: E402


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("初始管理员密码（至少 12 位）: ")
    second = getpass.getpass("再次输入: ")
    if first != second:
        raise SystemExit("两次密码输入不一致")
    return first


def main() -> int:
    parser = argparse.ArgumentParser(description="一次性创建首个超级管理员")
    parser.add_argument("--username", required=True)
    parser.add_argument("--real-name", default="超级管理员")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="从标准输入读取一行密码，适合 Secret Manager 管道",
    )
    args = parser.parse_args()

    username = args.username.strip()
    if not username or len(username) > 32:
        raise SystemExit("用户名长度必须为 1 到 32 个字符")
    password = _read_password(args.password_stdin)
    if len(password) < 12 or len(password.encode("utf-8")) > 72:
        raise SystemExit("密码必须至少 12 个字符且 UTF-8 编码不超过 72 字节")

    db = SessionLocal()
    lock_acquired = False
    try:
        dialect = db.get_bind().dialect.name
        if dialect == "mysql":
            lock_acquired = bool(
                db.execute(text("SELECT GET_LOCK('zjr_bootstrap_super_admin', 10)")).scalar()
            )
            if not lock_acquired:
                raise SystemExit("无法取得首管理员引导锁，请稍后重试")
        if db.query(Admin.id).count() != 0:
            raise SystemExit("admins 表非空，拒绝执行首管理员引导")
        admin = Admin(
            username=username,
            password_hash=hash_password(password),
            real_name=args.real_name.strip()[:32] or None,
            role="super_admin",
            must_change_password=False,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("首个超级管理员已安全创建。")
        return 0
    except BaseException:
        db.rollback()
        raise
    finally:
        if lock_acquired:
            try:
                db.execute(text("SELECT RELEASE_LOCK('zjr_bootstrap_super_admin')"))
            except Exception:
                pass
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
