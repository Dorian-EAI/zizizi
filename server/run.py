"""启动脚本 — uvicorn 服务器。

安全说明：
- 启动横幅不再打印管理员密码（避免进入容器日志/系统日志泄露凭据）
- 仅 development/testing 自动建表和写入示例数据
- staging/production 必须先通过 Alembic 建表，且不会写入示例师傅
- 默认账号密码仅在本地环境首次创建时输出
- 部署环境通过 scripts/bootstrap_super_admin.py 一次性创建首个管理员
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.config import settings
from init_db import ensure_initialized


def print_startup_banner():
    """打印启动横幅（不含敏感凭据）"""
    port = 8000
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " " * 18 + "🎯  服务启动成功！" + " " * 22 + "║")
    print("╠" + "═" * 58 + "╣")
    if settings.APP_DEBUG:
        print(f"║  🌐  API 文档:    http://localhost:{port}/docs" + " " * 18 + "║")
        print(f"║  📘  ReDoc:       http://localhost:{port}/redoc" + " " * 17 + "║")
    print(f"║  💊  健康检查:    http://localhost:{port}/health" + " " * 16 + "║")
    print(f"║  🔧  管理后台:    http://localhost:{port}/admin" + " " * 17 + "║")
    if not settings.is_deployed:
        print("╠" + "═" * 58 + "╣")
        print(f"║  👤  本地种子账号: {settings.ADMIN_DEFAULT_USER}" + " " * (31 - len(settings.ADMIN_DEFAULT_USER)) + "║")
    print("╚" + "═" * 58 + "╝")
    if settings.is_deployed:
        print("\n  💡  提示: 先执行 Alembic；空 admins 表用 bootstrap_super_admin.py 引导")
    else:
        print("\n  💡  提示: 本地环境会自动创建数据库表 + 种子数据")
    print(f"  🚦  模式: {'DEBUG（热重载）' if settings.APP_DEBUG else '非调试模式'}")
    print(f"  🛡️  环境: {settings.APP_ENV}\n")


if __name__ == "__main__":
    if not settings.is_deployed:
        ensure_initialized()
    print_startup_banner()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.APP_DEBUG,
        workers=1 if settings.APP_DEBUG else settings.WEB_CONCURRENCY,
        log_level="debug" if settings.APP_DEBUG else "info",
    )
