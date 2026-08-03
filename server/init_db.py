"""数据库初始化脚本 — 创建所有表 + 写入测试/种子数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal, Base
from app.config import settings
from app.models.user import User, Worker, Address
from app.models.order import Order, Bidding
from app.models.wallet import Transaction, PaymentOrder
from app.models.admin import Admin
from app.utils.security import hash_password


def create_tables():
    """创建所有表（需要先 import 所有模型才能在 Base.metadata 里注册）"""
    if settings.is_deployed:
        raise RuntimeError(
            "staging/production 禁止 create_all，请先执行 `alembic upgrade head`"
        )
    print("正在注册所有模型...")
    # 确保所有模型都被导入到 Base.metadata
    import app.models.user
    import app.models.order
    import app.models.wallet
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
    import app.models.insurance
    import app.models.deposit
    import app.models.lbs_track
    import app.models.extra_fee
    import app.models.annual_card
    import app.models.quality
    import app.models.training
    import app.models.support_ticket
    import app.models.pricing

    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("✅ 表创建完成")


def seed_demo_workers(db):
    """写入 2 个示例师傅（只在师傅表为空时写入，避免污染生产数据）"""
    if settings.is_deployed:
        raise RuntimeError("staging/production 禁止写入示例师傅")
    if db.query(Worker).count() > 0:
        print("⚠️  师傅表已有数据，跳过示例师傅写入")
        return
    demo1 = Worker(
        openid="demo_worker_openid_001",
        nickname="张师傅",
        avatar="",
        phone="13900139000",
        real_name="张建国",
        certified=2,
        skills='["防水维修","水电维修","空调维修"]',
        service_types='["electric","aircon","plumbing","circuit"]',
        rating=4.9,
        service_count=328,
        completed_orders=301,
        level=3,
        balance=880.0,
        is_online=True,
        service_area="广东省-深圳市-南山区;广东省-深圳市-福田区",
    )
    demo2 = Worker(
        openid="demo_worker_openid_002",
        nickname="李师傅",
        avatar="",
        phone="13700137000",
        real_name="李明",
        certified=2,
        skills='["管道疏通","水电维修","门窗维修"]',
        service_types='["electric","plumbing","door_window"]',
        rating=4.8,
        service_count=256,
        completed_orders=230,
        level=2,
        balance=620.0,
        is_online=True,
        service_area="广东省-深圳市-南山区;广东省-深圳市-宝安区",
    )
    db.add(demo1)
    db.add(demo2)
    print("✅ 示例师傅: 写入 2 个默认师傅（张师傅 / 李师傅）")


def ensure_initialized():
    """一键初始化：建表 + 写入种子数据（幂等，可重复调用）"""
    if settings.is_deployed:
        raise RuntimeError(
            "ensure_initialized 仅供 development/testing；部署环境必须使用 Alembic"
        )
    print("\n" + "=" * 60)
    print("  🚀  正在初始化数据库（首次运行自动建表 + 种子数据）")
    print("=" * 60 + "\n")
    create_tables()
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_default_services(db)
        seed_demo_workers(db)
        seed_default_pages_and_faqs(db)
        seed_default_point_rules(db)
        db.commit()
        print("\n✅ 数据库初始化完成\n")
    except Exception as e:
        db.rollback()
        print(f"❌ 数据库初始化失败: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()


def seed_admin(db):
    """初始化默认管理员账号（只创建一次）"""
    username = settings.ADMIN_DEFAULT_USER
    if db.query(Admin).filter(Admin.username == username).count() == 0:
        admin = Admin(
            username=username,
            password_hash=hash_password(settings.ADMIN_DEFAULT_PASSWORD),
            real_name="超级管理员",
            role="super_admin",
        )
        db.add(admin)
        if settings.is_deployed:
            print(f"✅ 管理员已创建: {username}（密码不写入部署日志）")
        else:
            print(f"✅ 管理员: {username} / {settings.ADMIN_DEFAULT_PASSWORD}")
    else:
        print(f"⚠️  管理员已存在: {username}")


def seed_default_services(db):
    """写入 8 类标准服务类型（只创建一次）"""
    from app.models.service import ServiceType
    if db.query(ServiceType).count() > 0:
        print("⚠️  服务类型已存在，跳过")
        return
    services = [
        {"key": "electric", "name": "水电维修", "category": "基础维修", "price_min": 80, "price_max": 200, "sort_order": 1},
        {"key": "aircon", "name": "空调维修", "category": "家电维修", "price_min": 100, "price_max": 300, "sort_order": 2},
        {"key": "appliance", "name": "家电维修", "category": "家电维修", "price_min": 100, "price_max": 400, "sort_order": 3},
        {"key": "plumbing", "name": "管道疏通", "category": "厨卫维修", "price_min": 70, "price_max": 180, "sort_order": 4},
        {"key": "door_window", "name": "门窗维修", "category": "家居维修", "price_min": 80, "price_max": 250, "sort_order": 5},
        {"key": "circuit", "name": "电路检修", "category": "基础维修", "price_min": 90, "price_max": 220, "sort_order": 6},
        {"key": "furniture", "name": "家具安装", "category": "家居维修", "price_min": 60, "price_max": 200, "sort_order": 7},
        {"key": "wall", "name": "墙面修补", "category": "装修维护", "price_min": 80, "price_max": 300, "sort_order": 8},
    ]
    for s in services:
        db.add(ServiceType(**s, is_active=True))
    print(f"✅ 服务类型: 写入 {len(services)} 类标准服务")


def seed_default_pages_and_faqs(db):
    """写入默认页面 + FAQ"""
    from app.services.content_service import seed_default_pages, seed_default_faqs
    from app.models.agreement import PageContent
    from app.models.faq import FAQCategory
    if db.query(PageContent).count() == 0:
        seed_default_pages(db)
        print("✅ 页面内容: 关于我们/用户协议/隐私政策/帮助中心")
    else:
        print("⚠️  页面内容已存在，跳过")
    if db.query(FAQCategory).count() == 0:
        seed_default_faqs(db)
        print("✅ FAQ: 5 大类 23 条")
    else:
        print("⚠️  FAQ 已存在，跳过")


def seed_default_point_rules(db):
    """初始化 4 条默认积分规则"""
    from app.services.point_service import ensure_rules
    from app.models.point import PointRule
    if db.query(PointRule).count() == 0:
        ensure_rules(db)
        print("✅ 积分规则: 4 条默认规则初始化")
    else:
        print("⚠️  积分规则已存在，跳过")


def seed_test_data():
    """写入开发测试数据（用户/师傅/地址/订单/竞价）"""
    db = SessionLocal()
    try:
        # 管理员 + 种子内容
        seed_admin(db)
        seed_default_services(db)
        seed_default_pages_and_faqs(db)
        seed_default_point_rules(db)
        db.commit()

        # 业务测试数据（有用户数据就跳过）
        if db.query(User).count() > 0:
            print("⚠️  数据库已有用户数据，跳过业务测试数据写入")
            return

        # 创建测试用户
        test_user = User(
            openid="test_user_openid_001",
            nickname="测试用户",
            avatar="",
            phone="13800138000",
            role="user",
            balance=500.0,
        )
        db.add(test_user)
        db.flush()

        # 创建测试地址
        from app.models.user import Address as UserAddress
        test_address = UserAddress(
            user_id=test_user.id,
            name="张三",
            phone="13800138000",
            province="广东省",
            city="深圳市",
            district="南山区",
            detail="科技园南区A栋1201室",
            label="家",
            is_default=True,
        )
        db.add(test_address)

        # 创建测试师傅
        test_worker = Worker(
            openid="test_worker_openid_001",
            nickname="张师傅",
            avatar="",
            phone="13900139000",
            real_name="张建国",
            certified=2,
            skills='["防水维修","水电维修","空调维修"]',
            rating=4.9,
            service_count=328,
            level=3,
            balance=880.0,
            is_online=True,
        )
        db.add(test_worker)

        test_worker2 = Worker(
            openid="test_worker_openid_002",
            nickname="李师傅",
            avatar="",
            phone="13700137000",
            real_name="李明",
            certified=2,
            skills='["管道疏通","水电维修"]',
            rating=4.8,
            service_count=256,
            level=2,
            balance=620.0,
            is_online=True,
        )
        db.add(test_worker2)
        db.flush()

        # 创建测试订单
        import json
        from datetime import datetime, timedelta
        test_order = Order(
            order_no="ORD20260728001",
            user_id=test_user.id,
            service_type="plumbing",
            service_name="管道疏通",
            description="厨房下水道堵塞，水流很慢",
            images=json.dumps([]),
            address=json.dumps({"name": "张三", "phone": "13800138000", "detail": "南山区科技园A栋1201"}),
            appoint_time=datetime.utcnow() + timedelta(hours=2),
            budget=150,
            urgent=False,
            status="pending",
        )
        db.add(test_order)
        db.flush()

        # 创建测试竞价
        test_bidding = Bidding(
            order_id=test_order.id,
            worker_id=test_worker.id,
            price=120,
            message="有经验，30分钟可到",
            eta="30分钟",
        )
        db.add(test_bidding)

        db.commit()
        print("✅ 业务测试数据写入完成")
        print(f"   测试用户 ID: {test_user.id} (openid: {test_user.openid})")
        print(f"   测试师傅 ID: {test_worker.id} (openid: {test_worker.openid})")
        print(f"   测试订单号: {test_order.order_no}")

    except Exception as e:
        db.rollback()
        print(f"❌ 写入测试数据失败: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_tables()
    print()
    seed_test_data()
    print("\n🎉 数据库初始化全部完成！")
    print("\n下一步：")
    print("  1. 复制 cp .env.example .env 并填入 MySQL 密码")
    print("  2. 启动服务：python run.py")
    print("  3. 访问 http://localhost:8000/docs 查看 Swagger 文档")
    print("  4. 运营后台登录：admin / admin123")
