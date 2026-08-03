"""APScheduler 定时任务封装"""

from functools import wraps
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# 全局调度器实例
_scheduler: Optional[BackgroundScheduler] = None


def _distributed_guard(func, lock_name: str):
    """为每次任务执行增加跨进程 Redis 锁。"""
    @wraps(func)
    def guarded(*args, **kwargs):
        from app.utils.redis_client import redis_client

        lock_key = f"scheduler:lock:{lock_name}"
        token = redis_client.acquire_lock(lock_key, expire_seconds=900)
        if not token:
            return None
        try:
            return func(*args, **kwargs)
        finally:
            redis_client.release_lock(lock_key, token)

    return guarded


def get_scheduler() -> BackgroundScheduler:
    """获取或创建全局调度器"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={"misfire_grace_time": 300, "coalesce": True},
        )
    return _scheduler


def start_scheduler():
    """启动调度器（应用启动时调用）"""
    from app.config import settings

    if not settings.SCHEDULER_ENABLED:
        return
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        print("✅ APScheduler 定时任务调度器已启动")


def shutdown_scheduler():
    """关闭调度器（应用关闭时调用）"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("🛑 APScheduler 已关闭")
    # APScheduler 已 shutdown 的实例不可安全复用；测试重启或优雅重载时创建新实例。
    _scheduler = None


def add_cron_job(func, cron_expr: str, *args, job_id: Optional[str] = None, **kwargs):
    """添加 cron 表达式任务
    例：add_cron_job(my_task, '0 2 * * *') 每天凌晨 2 点
    """
    sched = get_scheduler()
    minute, hour, day, month, day_of_week = cron_expr.strip().split()
    trigger = CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )
    resolved_job_id = job_id or func.__name__
    return sched.add_job(
        _distributed_guard(func, resolved_job_id), trigger, args=args, kwargs=kwargs,
        id=resolved_job_id, replace_existing=True, max_instances=1,
    )


def add_interval_job(func, seconds: int, *args, job_id: Optional[str] = None, **kwargs):
    """添加间隔任务
    例：add_interval_job(my_task, 300) 每 5 分钟
    """
    sched = get_scheduler()
    resolved_job_id = job_id or func.__name__
    return sched.add_job(
        _distributed_guard(func, resolved_job_id), IntervalTrigger(seconds=seconds), args=args, kwargs=kwargs,
        id=resolved_job_id, replace_existing=True, max_instances=1,
    )
