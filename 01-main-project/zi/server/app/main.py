"""FastAPI 应用入口"""

import os
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import engine, Base
from app.utils.response import success, error
from app.utils.logger import get_logger
from app.utils.scheduler import start_scheduler, shutdown_scheduler
from app.utils.security_middleware import (
    SecurityHeadersMiddleware,
    get_cors_origins,
    should_enable_trusted_host,
    get_allowed_hosts,
)
from app.utils.rate_limit import register_limiter, limiter, SLOWAPI_AVAILABLE
from app.tasks.jobs import (
    auto_cancel_expired_orders,
    auto_accept_overdue_acceptances,
    expire_coupons,
    daily_stats_snapshot,
    auto_approve_reviews,
    check_expired_annual_cards,
    send_quality_inspection_reminders,
    auto_close_resolved_tickets,
    expire_insurance_policies,
    remind_overdue_extra_fees,
    audit_deposit_refunds,
    reconcile_wechat_payments,
    reconcile_wechat_refunds,
    settle_worker_pending_income,
    cleanup_expired_agent_sessions,
)

logger = get_logger("app.main")
error_logger = get_logger("app.error")
_SERVER_ROOT = os.path.dirname(os.path.dirname(__file__))

if settings.is_deployed:
    from app.utils.deployment_probe import assert_deployment_dependencies

    assert_deployment_dependencies()


def _migration_head_status() -> tuple[bool, set[str], set[str]]:
    """返回数据库 revision 与代码 Alembic head 是否完全一致。"""
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    alembic_config = Config(os.path.join(_SERVER_ROOT, "alembic.ini"))
    expected = set(ScriptDirectory.from_config(alembic_config).get_heads())
    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    return current == expected, current, expected

# 必须先导入所有模型，确保 Base.metadata 包含完整表定义
import app.models.user
import app.models.order
import app.models.wallet
import app.models.worker_fund
import app.models.coupon
import app.models.message
import app.models.admin
import app.models.service
import app.models.favorite
import app.models.point
import app.models.feedback
import app.models.faq
import app.models.agreement
import app.models.setting
import app.models.review

# v4.0 新增模型
import app.models.insurance
import app.models.deposit
import app.models.lbs_track
import app.models.extra_fee
import app.models.annual_card
import app.models.quality
import app.models.training
import app.models.support_ticket
import app.models.pricing
import app.models.agent

# 导入路由
from app.api.auth import router as auth_router
from app.api.orders import router as orders_router
from app.api.ai import router as ai_router
from app.api.agent import router as agent_router
from app.api.wallet import router as wallet_router
from app.api.reviews import router as reviews_router
from app.api.coupon import router as coupon_router
from app.api.upload import router as upload_router
from app.api.wxpay import router as wxpay_router
from app.api.admin import router as admin_router
from app.api.messages import router as messages_router
from app.api.member import router as member_router
from app.api.favorite import router as favorite_router
from app.api.services import router as services_router, catalog_router as catalog_router
from app.api.worker_orders import router as worker_orders_router
from app.api.points import router as points_router
from app.api.feedback import router as feedback_router
from app.api.pages import router as pages_router
from app.api.settings import router as settings_router

# v4.0 新增路由
from app.api.insurance import router as insurance_router
from app.api.deposit import router as deposit_router
from app.api.lbs_track import router as lbs_track_router
from app.api.extra_fee import router as extra_fee_router
from app.api.annual_card import router as annual_card_router
from app.api.quality import router as quality_router
from app.api.training import router as training_router
from app.api.support_ticket import router as support_ticket_router
from app.api.pricing import router as pricing_router
from app.api.export import router as export_router
from app.api.finance import router as finance_router
from app.api.sms import router as sms_router
from app.api.map import router as map_router

# 开发/测试模式：若未使用 Alembic 迁移则自动建表（兼容首次启动）
# 体验/生产环境必须使用 `alembic upgrade head` 管理 schema
def _maybe_auto_create_tables():
    """开发/测试可自动建表；体验/生产必须由 Alembic 管理。"""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        if settings.is_deployed:
            raise RuntimeError(
                "部署数据库缺少 alembic_version，请先执行 `alembic upgrade head`；"
                "为避免不可追踪的结构变更，服务拒绝自动 create_all。"
            )
        Base.metadata.create_all(bind=engine)
    elif settings.is_deployed:
        migration_ok, current, expected = _migration_head_status()
        if not migration_ok:
            raise RuntimeError(
                "部署数据库 Alembic 版本未到代码 head，拒绝启动："
                f"current={sorted(current)} expected={sorted(expected)}"
            )

_maybe_auto_create_tables()


def _startup_seed_data():
    """仅在开发/测试环境写入种子数据（幂等，重复调用安全）。"""
    if settings.is_deployed:
        return

    from app.database import SessionLocal
    from init_db import (
        create_tables,
        seed_admin,
        seed_default_services,
        seed_default_pages_and_faqs,
        seed_default_point_rules,
    )
    create_tables()
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_default_services(db)
        seed_default_pages_and_faqs(db)
        seed_default_point_rules(db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("启动种子数据写入失败")
    finally:
        db.close()

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动定时任务，关闭时清理"""
    _startup_seed_data()
    scheduler_started = False
    if settings.SCHEDULER_ENABLED:
        start_scheduler()
        scheduler_started = True
        # 注册定时任务。多副本部署时应只在独立 scheduler 实例开启本开关。
        from app.utils.scheduler import add_cron_job, add_interval_job
        add_interval_job(auto_cancel_expired_orders, seconds=600)   # 每 10 分钟
        add_interval_job(auto_accept_overdue_acceptances, seconds=3600)  # 每小时自动验收
        add_interval_job(expire_coupons, seconds=3600)              # 每小时
        add_interval_job(auto_approve_reviews, seconds=3600)        # 每小时自动审核评价
        add_cron_job(daily_stats_snapshot, "0 2 * * *")             # 每天凌晨 2 点
        add_cron_job(check_expired_annual_cards, "0 3 * * *")       # 每天凌晨 3 点检查过期年卡
        add_interval_job(send_quality_inspection_reminders, seconds=1800)  # 每 30 分钟发送回访提醒
        add_cron_job(auto_close_resolved_tickets, "0 4 * * *")      # 每天凌晨 4 点自动关闭已解决工单
        add_cron_job(expire_insurance_policies, "15 3 * * *")       # 每天凌晨 3:15 处理过期保单
        add_interval_job(remind_overdue_extra_fees, seconds=3600)    # 每小时统计超时补差价并提醒升级，不改状态
        add_cron_job(audit_deposit_refunds, "30 3 * * *")           # 每天凌晨 3:30 审核保证金退款
        add_interval_job(reconcile_wechat_payments, seconds=300)     # 每 5 分钟支付查单/安全释放预留
        add_interval_job(reconcile_wechat_refunds, seconds=300)      # 每 5 分钟退款对账/有界重试
        add_interval_job(settle_worker_pending_income, seconds=300)  # 每 5 分钟结算到期师傅收入
        add_cron_job(cleanup_expired_agent_sessions, "40 3 * * *")   # 每天凌晨 3:40 清理过期 AI 会话
    try:
        yield
    finally:
        if scheduler_started:
            shutdown_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
    lifespan=lifespan,
)

# 注册限流（必须早于路由注册）
register_limiter(app)


# ===== 安全中间件 =====

# 1. TrustedHostMiddleware — 防 Host 头注入
# 生产环境或显式配置 ALLOWED_HOSTS 时启用
if should_enable_trusted_host():
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=get_allowed_hosts(),
    )

# 2. CORS — 显式白名单，不再使用 ["*"] + allow_credentials=True 的危险组合
# 微信小程序请求不走浏览器 CORS，但仍需为 H5/管理后台 Web 端预留
_cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=bool(_cors_origins) and "*" not in _cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Requested-With",
        "Idempotency-Key",
    ],
    expose_headers=["X-Total-Count"],
    max_age=600,
)

# 3. SecurityHeadersMiddleware — 安全响应头
app.add_middleware(SecurityHeadersMiddleware)


# 全局异常处理：HTTPException（4xx/5xx 记录 warning）
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理，4xx/5xx 写 warning 日志"""
    log_msg = f"HTTP {exc.status_code} {request.method} {request.url.path}: {exc.detail}"
    if 400 <= exc.status_code < 500:
        logger.warning(log_msg)
    elif exc.status_code >= 500:
        error_logger.warning(log_msg)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "msg": str(exc.detail) if exc.detail else "",
            "detail": exc.detail if settings.APP_DEBUG else None,
        },
    )


# 全局异常处理：兜底 Exception（500，写 error 日志 + 完整 traceback）
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底，完整 traceback 写入 error.log"""
    tb_str = traceback.format_exc()
    error_logger.error(
        f"Unhandled Exception {request.method} {request.url.path}: {exc}\n{tb_str}",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    if settings.APP_DEBUG:
        traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "msg": "服务器内部错误",
            "detail": str(exc) if settings.APP_DEBUG else None,
        },
    )


# 健康检查（对外仅返回 status，不泄露内部路径/配置）
@app.get("/health")
async def health():
    return success(data={
        "status": "ok",
        "version": "1.0.0",
    })


@app.get("/ready")
async def readiness():
    """就绪探针：体验/生产环境要求数据库迁移与 Redis 均可用。"""
    from sqlalchemy import inspect, text
    from app.utils.redis_client import redis_client

    db_ok = False
    migration_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
        if "alembic_version" in inspect(engine).get_table_names():
            migration_ok, _, _ = _migration_head_status()
    except Exception:
        pass

    redis_ok = redis_client.ping()
    schema_ok = migration_ok or not settings.is_deployed
    ready = db_ok and schema_ok and (redis_ok or not settings.is_deployed)
    payload = {
        "code": 0 if ready else 503,
        "message": "ready" if ready else "not ready",
        "data": {"status": "ready" if ready else "not_ready"},
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)

# 仅开发/测试挂载本地上传目录；体验/生产必须使用对象存储，避免应用进程暴露 PII 文件。
if not settings.is_deployed:
    from app.services.upload_service import _get_upload_dir

    _local_upload_dir = _get_upload_dir()
    os.makedirs(_local_upload_dir, exist_ok=True)
    app.mount(settings.UPLOAD_URL_PREFIX, StaticFiles(directory=_local_upload_dir), name="uploads")

# 挂载内置管理后台（Vue + Element Plus 单页应用）
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if settings.ENABLE_BUILTIN_ADMIN and os.path.isdir(_STATIC_DIR):
    app.mount("/admin/static", StaticFiles(directory=_STATIC_DIR), name="admin_static")


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """内置 Web 管理后台入口（只允许本地开发显式开启）。"""
    if not settings.ENABLE_BUILTIN_ADMIN:
        raise HTTPException(status_code=404, detail="管理后台未在此服务启用")
    admin_html = os.path.join(_STATIC_DIR, "admin.html")
    if not os.path.isfile(admin_html):
        return HTMLResponse("<h1>管理后台文件不存在</h1>", status_code=404)
    with open(admin_html, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# 注册路由（26 组）
app.include_router(auth_router)
app.include_router(orders_router)
app.include_router(ai_router)
app.include_router(agent_router)
app.include_router(wallet_router)
app.include_router(coupon_router)
app.include_router(upload_router)
app.include_router(wxpay_router)
app.include_router(admin_router)
app.include_router(messages_router)
app.include_router(member_router)
app.include_router(favorite_router)
app.include_router(services_router)
app.include_router(catalog_router)
app.include_router(worker_orders_router)
app.include_router(points_router)
app.include_router(feedback_router)
app.include_router(pages_router)
app.include_router(settings_router)
app.include_router(reviews_router)

# v4.0 新增路由
app.include_router(insurance_router)
app.include_router(deposit_router)
app.include_router(lbs_track_router)
app.include_router(extra_fee_router)
app.include_router(annual_card_router)
app.include_router(quality_router)
app.include_router(training_router)
app.include_router(support_ticket_router)
app.include_router(pricing_router)
app.include_router(export_router)
app.include_router(finance_router)
app.include_router(sms_router)
app.include_router(map_router)
