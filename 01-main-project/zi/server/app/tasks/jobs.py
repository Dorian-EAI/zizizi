"""业务定时任务定义"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.agent import AgentSession
from app.models.order import Order
from app.models.coupon import Coupon
from app.utils.logger import get_logger

logger = get_logger("tasks.jobs")
_MUTATION_BATCH_SIZE = 500
_PAYMENT_BATCH_SIZE = 200


def _get_db() -> Session:
    return SessionLocal()


# ========== 订单相关 ==========

def auto_cancel_expired_orders():
    """自动取消超过 24 小时未接单的订单"""
    db = _get_db()
    try:
        deadline = datetime.utcnow() - timedelta(hours=24)
        expired = (
            db.query(Order)
            .filter(Order.status == "pending", Order.created_at < deadline)
            .order_by(Order.created_at.asc())
            .limit(_MUTATION_BATCH_SIZE)
            .all()
        )
        count = 0
        for order in expired:
            order.status = "cancelled"
            order.cancelled_at = datetime.utcnow()
            count += 1
        db.commit()
        if count > 0:
            logger.info(f"[定时任务] 自动取消 {count} 条过期未接单订单")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 自动取消订单失败: {e}")
    finally:
        db.close()


def auto_accept_overdue_acceptances():
    """验收观察期到期自动验收。"""
    db = _get_db()
    try:
        from app.services.order_service import auto_accept_overdue_orders

        count = auto_accept_overdue_orders(db)
        db.commit()
        if count > 0:
            logger.info(f"[定时任务] 自动验收 {count} 条超期订单")
    except Exception as exc:
        db.rollback()
        logger.error(f"[定时任务] 自动验收失败: {exc}")
    finally:
        db.close()


def auto_complete_orders():
    """自动确认完成：师傅标记完成后超过 72 小时用户未确认的订单"""
    db = _get_db()
    try:
        deadline = datetime.utcnow() - timedelta(hours=72)
        orders = (
            db.query(Order)
            .filter(Order.status == "accepted", Order.completed_at < deadline)
            .order_by(Order.completed_at.asc())
            .limit(_MUTATION_BATCH_SIZE)
            .all()
        )
        count = 0
        for order in orders:
            order.status = "completed"
            count += 1
        db.commit()
        if count > 0:
            logger.info(f"[定时任务] 自动完成 {count} 条订单")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 自动完成订单失败: {e}")
    finally:
        db.close()


# ========== 优惠券相关 ==========

def expire_coupons():
    """将过期优惠券状态更新为 expired"""
    db = _get_db()
    try:
        now = datetime.utcnow()
        expired = (
            db.query(Coupon)
            .filter(Coupon.status == "active", Coupon.expire_at < now)
            .order_by(Coupon.expire_at.asc())
            .limit(_MUTATION_BATCH_SIZE)
            .all()
        )
        count = 0
        for c in expired:
            c.status = "expired"
            count += 1
        db.commit()
        if count > 0:
            logger.info(f"[定时任务] 过期 {count} 张优惠券")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 优惠券过期处理失败: {e}")
    finally:
        db.close()


# ========== 统计相关 ==========

def daily_stats_snapshot():
    """每日统计快照（包含财务汇总）"""
    db = _get_db()
    try:
        from app.models.order import Order
        from app.models.user import User, Worker
        from app.services import finance_service

        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)

        order_count = db.query(Order).filter(
            Order.created_at >= datetime.combine(today, datetime.min.time())
        ).count()
        user_count = db.query(User).count()
        worker_count = db.query(Worker).count()

        # 昨日按日财务统计 + 平台整体汇总
        daily = finance_service.get_daily_stats(db, yesterday, yesterday)
        summary = finance_service.get_platform_summary(db)

        logger.info(
            f"[每日统计] 日期={today}, 新订单={order_count}, "
            f"总用户={user_count}, 总师傅={worker_count}, "
            f"昨日财务={daily[0] if daily else {}}, 平台汇总={summary}"
        )
    except Exception as e:
        logger.error(f"[定时任务] 每日统计失败: {e}")
    finally:
        db.close()


# ========== 评价相关 ==========

def auto_approve_reviews():
    """自动审核通过超过 24 小时的 pending 评价"""
    db = _get_db()
    try:
        from app.services.review_service import auto_approve_pending_reviews
        count = auto_approve_pending_reviews(db, hours=24)
        if count > 0:
            logger.info(f"[定时任务] 自动审核通过 {count} 条评价")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 评价自动审核失败: {e}")
    finally:
        db.close()


# ========== 年卡相关 ==========

def check_expired_annual_cards():
    """标记已过期的年卡"""
    db = _get_db()
    try:
        from app.services.annual_card_service import check_expiry
        check_expiry(db)
        logger.info("[定时任务] 年卡过期检查完成")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 年卡过期检查失败: {e}")
    finally:
        db.close()


def expire_insurance_policies():
    """将已过保障期且仍有效的保单标记为 expired。"""
    db = _get_db()
    try:
        from app.models.insurance import InsurancePolicy
        count = db.query(InsurancePolicy).filter(
            InsurancePolicy.status == "active",
            InsurancePolicy.expired_at < datetime.utcnow(),
        ).update({"status": "expired"}, synchronize_session=False)
        db.commit()
        if count:
            logger.info(f"[定时任务] 过期 {count} 份安心保保单")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 保单过期处理失败: {e}")
    finally:
        db.close()


def remind_overdue_extra_fees():
    """统计超过 24 小时未响应的补差价申请，提醒运营升级但不改状态。"""
    db = _get_db()
    try:
        from app.services.extra_fee_service import get_overdue_pending_ids

        overdue_ids = get_overdue_pending_ids(db)
        if overdue_ids:
            logger.warning(
                f"[定时任务] {len(overdue_ids)} 笔补差价申请超时待提醒/升级，"
                f"记录ID={overdue_ids[:100]}"
            )
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 补差价超时提醒检查失败: {e}")
    finally:
        db.close()


def audit_deposit_refunds():
    """处理已满足七天审核期的保证金退款申请。"""
    from app.config import settings
    if settings.APP_ENV.lower() != "development" or not settings.WX_PAY_MOCK_ENABLED:
        logger.info("[定时任务] 保证金真实退款通道未启用，保留待审核申请")
        return
    db = _get_db()
    try:
        from app.models.deposit import WorkerDeposit
        from app.services.deposit_service import process_refund
        deadline = datetime.utcnow() - timedelta(days=7)
        worker_ids = [row[0] for row in db.query(WorkerDeposit.worker_id).filter(
            WorkerDeposit.status == "refunding",
            WorkerDeposit.refund_requested_at <= deadline,
        ).order_by(WorkerDeposit.refund_requested_at.asc()).limit(_PAYMENT_BATCH_SIZE).all()]
        db.close()
        db = None
        for worker_id in worker_ids:
            worker_db = _get_db()
            try:
                process_refund(worker_db, worker_id)
            finally:
                worker_db.close()
        if worker_ids:
            logger.info(f"[定时任务] 完成 {len(worker_ids)} 笔保证金退款审核")
    except Exception as e:
        if db is not None:
            db.rollback()
        logger.error(f"[定时任务] 保证金退款审核失败: {e}")
    finally:
        if db is not None:
            db.close()


# ========== 微信支付/退款对账 ==========

def reconcile_wechat_payments():
    """查单并处理超时支付；任何网络/查单失败都不会释放用户余额。"""
    db = _get_db()
    try:
        from app.services.wechat_pay_service import reconcile_pending_wechat_payments

        stats = reconcile_pending_wechat_payments(db)
        if stats["checked"] or stats["errors"]:
            logger.info(f"[定时任务] 微信支付对账: {stats}")
    except Exception as exc:
        db.rollback()
        logger.error(f"[定时任务] 微信支付对账失败: {exc}")
    finally:
        db.close()


def reconcile_wechat_refunds():
    """查询退款终态，并对微信查无记录的退款执行有界幂等重试。"""
    db = _get_db()
    try:
        from app.services.wechat_pay_service import reconcile_pending_wechat_refunds

        stats = reconcile_pending_wechat_refunds(db)
        if stats["checked"] or stats["errors"]:
            logger.info(f"[定时任务] 微信退款对账: {stats}")
    except Exception as exc:
        db.rollback()
        logger.error(f"[定时任务] 微信退款对账失败: {exc}")
    finally:
        db.close()


# ========== 师傅收入结算 ==========

def settle_worker_pending_income():
    """将超过结算等待期的师傅待结算收入转入可提现余额。"""
    db = _get_db()
    try:
        from app.services.worker_fund_service import settle_pending_income

        stats = settle_pending_income(db)
        db.commit()
        if stats["settled_count"]:
            logger.info(f"[定时任务] 师傅收入结算: {stats}")
    except Exception as exc:
        db.rollback()
        logger.error(f"[定时任务] 师傅收入结算失败: {exc}")
    finally:
        db.close()


# ========== 质检回访相关 ==========

def send_quality_inspection_reminders():
    """发送质检回访提醒（订单完成超过24小时且未发送）"""
    db = _get_db()
    try:
        from app.services.quality_service import get_inspections_to_send
        from app.services.message_service import send_inbox_message
        inspections = get_inspections_to_send(db)
        count = 0
        for insp in inspections:
            from datetime import datetime
            send_inbox_message(
                db,
                owner_type="user",
                owner_id=insp.user_id,
                msg_type="order",
                title="服务回访邀请",
                content="请为最近完成的服务提交回访评价，您的反馈会用于服务质检。",
                payload={"inspection_id": insp.id, "order_id": insp.order_id},
                commit=False,
            )
            # 站内消息与 send_at 在同一事务提交，失败时可由下轮安全重试。
            insp.send_at = datetime.utcnow()
            count += 1
        db.commit()
        if count > 0:
            logger.info(f"[定时任务] 发送 {count} 条质检回访提醒")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 质检回访提醒失败: {e}")
    finally:
        db.close()


# ========== 工单相关 ==========

def auto_close_resolved_tickets():
    """自动关闭已解决超过7天的工单"""
    db = _get_db()
    try:
        from datetime import datetime, timedelta
        from app.models.support_ticket import SupportTicket
        deadline = datetime.utcnow() - timedelta(days=7)
        tickets = db.query(SupportTicket).filter(
            SupportTicket.status == "resolved",
            SupportTicket.resolved_at < deadline,
        ).order_by(SupportTicket.resolved_at.asc()).limit(_MUTATION_BATCH_SIZE).all()
        count = 0
        for t in tickets:
            t.status = "closed"
            t.closed_at = datetime.utcnow()
            count += 1
        db.commit()
        if count > 0:
            logger.info(f"[定时任务] 自动关闭 {count} 条已解决工单")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 工单自动关闭失败: {e}")
    finally:
        db.close()


# ========== AI 下单会话相关 ==========

def cleanup_expired_agent_sessions():
    """清理超过 30 天未再使用的 AI 下单会话，控制状态表体积。"""
    db = _get_db()
    try:
        deadline = datetime.utcnow() - timedelta(days=30)
        count = (
            db.query(AgentSession)
            .filter(AgentSession.updated_at < deadline)
            .delete(synchronize_session=False)
        )
        db.commit()
        if count > 0:
            logger.info(f"[定时任务] 清理 {count} 条过期 AI 下单会话")
    except Exception as e:
        db.rollback()
        logger.error(f"[定时任务] 清理 AI 下单会话失败: {e}")
    finally:
        db.close()
