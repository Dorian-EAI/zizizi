"""服务类型相关路由"""

import json
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.database import get_db
from app.schemas.service import (
    ServiceTypeCreateRequest,
    ServiceTypeDetailResponse,
    ServiceTypeListResponse,
    ToggleServiceActiveRequest,
)
from app.services import service_service, admin_service
from app.utils.response import success
from app.models.user import Worker
from app.models.service import ServiceType
from app.models.order import Order
from app.dependencies import get_current_admin, require_admin_operator, require_super_admin

router = APIRouter(prefix="/api/services", tags=["服务类型"])
catalog_router = APIRouter(prefix="/api/catalog", tags=["服务目录"])


def _parse_json_field(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _service_to_detail_dict(svc):
    return {
        "id": svc.id,
        "key": svc.key,
        "name": svc.name,
        "icon": svc.icon,
        "banner": svc.banner,
        "category": svc.category,
        "price_min": svc.price_min,
        "price_max": svc.price_max,
        "price_unit": svc.price_unit,
        "description": svc.description,
        "process_steps": _parse_json_field(svc.process_steps),
        "faq": _parse_json_field(svc.faq),
        "cases": _parse_json_field(svc.cases),
        # 扩展图文
        "intro_video": svc.intro_video,
        "service_images": _parse_json_field(svc.service_images),
        "detail_sections": _parse_json_field(svc.detail_sections),
        "service_standards": _parse_json_field(svc.service_standards),
        "price_details": _parse_json_field(svc.price_details),
        "pricing_modes": _parse_json_field(svc.pricing_modes) or ["bidding"],
        "pricing_schema": _parse_json_field(svc.pricing_schema),
        "service_boundary": _parse_json_field(svc.service_boundary),
        "risk_confirmation": _parse_json_field(svc.risk_confirmation),
        "warranty_days": int(svc.warranty_days or 0),
        "sort_order": int(svc.sort_order or 0),
        "is_active": bool(svc.is_active),
    }


def _service_to_list_dict(svc):
    return {
        "id": svc.id,
        "key": svc.key,
        "name": svc.name,
        "icon": svc.icon,
        "banner": svc.banner,
        "category": svc.category,
        "price_min": svc.price_min,
        "price_max": svc.price_max,
        "price_unit": svc.price_unit,
        "pricing_modes": _parse_json_field(svc.pricing_modes) or ["bidding"],
        "warranty_days": int(svc.warranty_days or 0),
        "sort_order": int(svc.sort_order or 0),
        "is_active": svc.is_active,
    }


def _worker_to_dict(w: Worker, extra: dict = None):
    skills = _parse_json_field(w.skills) or []
    display_name = w.nickname or ((w.real_name[:1] + "师傅") if w.real_name else f"师傅{w.id}")
    return {
        "id": w.id,
        "name": display_name,
        "nickname": w.nickname,
        "avatar": w.avatar,
        "certified": w.certified,  # 0未认证 1审核中 2已认证 3不通过
        "skills": skills,
        "rating": round(float(w.rating or 5.0), 1),
        "service_count": int(w.service_count or 0),
        "completed_orders": int(w.completed_orders or 0),
        "level": int(w.level or 1),
        "is_online": bool(w.is_online),
        "service_area": w.service_area,
        **(extra or {}),
    }


# ============================= 公开接口（小程序端） =============================


@router.get("")
async def list_services(
    category: Optional[str] = Query(None, description="按分类筛选，如 家电维修"),
    keyword: Optional[str] = Query(None, description="按名称/描述搜索"),
    db: Session = Depends(get_db),
):
    """获取启用的服务类型列表（支持分类+关键字筛选）"""
    q = db.query(ServiceType).filter(ServiceType.is_active == True)  # noqa: E712
    if category:
        q = q.filter(ServiceType.category == category)
    if keyword:
        k = f"%{keyword}%"
        q = q.filter(or_(ServiceType.name.like(k), ServiceType.description.like(k), ServiceType.category.like(k)))
    services = q.order_by(ServiceType.sort_order.asc(), ServiceType.id.asc()).limit(500).all()
    data = [_service_to_list_dict(s) for s in services]
    return success(data=data)


@router.get("/categories")
async def list_categories(db: Session = Depends(get_db)):
    """获取服务分类列表（聚合）"""
    rows = (
        db.query(
            ServiceType.category.label("name"),
            func.count(ServiceType.id).label("count"),
            func.max(ServiceType.sort_order).label("sort_weight"),
        )
        .filter(ServiceType.is_active == True)  # noqa: E712
        .group_by(ServiceType.category)
        .order_by(func.count(ServiceType.id).desc())
        .limit(200)
        .all()
    )
    data = [
        {"name": r.name or "其他", "count": int(r.count or 0), "sort_weight": int(r.sort_weight or 0)}
        for r in rows
    ]
    return success(data=data)


@router.get("/hot-tags")
async def list_hot_tags(db: Session = Depends(get_db)):
    """热门搜索标签（取分类名 + 服务名）"""
    svcs = (
        db.query(ServiceType)
        .filter(ServiceType.is_active == True)  # noqa: E712
        .order_by(ServiceType.sort_order.asc())
        .limit(10)
        .all()
    )
    tags = []
    for s in svcs:
        if s.category and s.category not in tags:
            tags.append(s.category)
        if s.name and s.name not in tags:
            tags.append(s.name)
    # 兜底通用标签
    default_tags = ["漏水", "跳闸", "空调不制冷", "下水道堵", "换锁", "灯具安装", "热水器", "冰箱", "洗衣机"]
    for t in default_tags:
        if t not in tags:
            tags.append(t)
    return success(data=tags[:12])


@router.get("/search")
async def search_services(
    keyword: str = Query(..., min_length=1, description="搜索关键字"),
    db: Session = Depends(get_db),
):
    """搜索服务类型 / 分类 / 师傅"""
    k = f"%{keyword}%"
    services = (
        db.query(ServiceType)
        .filter(
            ServiceType.is_active == True,  # noqa: E712
            or_(ServiceType.name.like(k), ServiceType.description.like(k), ServiceType.category.like(k)),
        )
        .limit(20)
        .all()
    )
    workers = (
        db.query(Worker)
        .filter(
            Worker.is_active == True,  # noqa: E712
            Worker.certified == 2,
            or_(
                Worker.nickname.like(k),
                Worker.real_name.like(k),
                Worker.skills.like(k),
                Worker.service_area.like(k),
            ),
        )
        .limit(10)
        .all()
    )
    data = {
        "services": [_service_to_list_dict(s) for s in services],
        "workers": [_worker_to_dict(w) for w in workers],
    }
    return success(data=data)


# ============================= 服务目录（v6.3 /api/catalog） =============================


@catalog_router.get("/services")
async def list_catalog_services(
    category: Optional[str] = Query(None, description="按分类筛选，如 家电维修"),
    keyword: Optional[str] = Query(None, description="按名称/描述搜索"),
    db: Session = Depends(get_db),
):
    """服务目录与 SKU 列表，返回允许的定价模式与质保期。"""
    q = db.query(ServiceType).filter(ServiceType.is_active == True)  # noqa: E712
    if category:
        q = q.filter(ServiceType.category == category)
    if keyword:
        k = f"%{keyword}%"
        q = q.filter(
            or_(
                ServiceType.name.like(k),
                ServiceType.description.like(k),
                ServiceType.category.like(k),
            )
        )
    services = q.order_by(ServiceType.sort_order.asc(), ServiceType.id.asc()).limit(500).all()
    return success(data=[_service_to_list_dict(s) for s in services])


@catalog_router.get("/services/{service_id}/schema")
async def get_catalog_schema(service_id: int, db: Session = Depends(get_db)):
    """SKU 必选属性、加价项、服务边界、风险确认书与默认质保期。"""
    svc = (
        db.query(ServiceType)
        .filter(ServiceType.id == service_id, ServiceType.is_active == True)  # noqa: E712
        .first()
    )
    if not svc:
        raise HTTPException(status_code=404, detail="服务类型不存在或已停用")
    data = _service_to_detail_dict(svc)
    data["pricing_modes"] = _parse_json_field(svc.pricing_modes) or ["bidding"]
    return success(data=data)


# ============================= 师傅相关（/api/services/workers/*） =============================


@router.get("/platform-stats")
async def platform_stats(db: Session = Depends(get_db)):
    """首页公开聚合指标，仅返回不可反查个人的统计数据。"""
    worker_count, average_rating = (
        db.query(func.count(Worker.id), func.avg(Worker.rating))
        .filter(Worker.is_active == True, Worker.certified == 2)  # noqa: E712
        .one()
    )
    recent_accepts = (
        db.query(Order.created_at, Order.accepted_at)
        .filter(Order.accepted_at.isnot(None), Order.created_at.isnot(None))
        .order_by(Order.accepted_at.desc())
        .limit(1000)
        .all()
    )
    response_seconds = [
        max(0, int((accepted_at - created_at).total_seconds()))
        for created_at, accepted_at in recent_accepts
        if created_at and accepted_at
    ]
    avg_response_seconds = (
        round(sum(response_seconds) / len(response_seconds)) if response_seconds else None
    )
    rating = round(float(average_rating or 0), 2)
    return success(data={
        "certified_worker_count": int(worker_count or 0),
        "average_rating": rating,
        "satisfaction_rate": round(rating / 5 * 100, 1) if rating else None,
        "average_response_seconds": avg_response_seconds,
    })


@router.get("/workers/recommend")
async def recommend_workers(
    limit: int = Query(8, ge=1, le=20, description="返回数量"),
    service_key: Optional[str] = Query(None, description="按可接服务类型筛选"),
    db: Session = Depends(get_db),
):
    """首页推荐师傅（综合评分 / 等级 / 服务次数排序，可按服务类型筛选）"""
    q = db.query(Worker).filter(
        Worker.is_active == True,
        Worker.is_online == True,
        Worker.certified == 2,
    )  # noqa: E712
    if service_key:
        sk = f"%{service_key}%"
        q = q.filter(Worker.service_types.like(sk))
    workers = q.order_by(Worker.rating.desc(), Worker.level.desc(), Worker.service_count.desc()).limit(limit).all()
    data = [_worker_to_dict(w, {"is_recommended": True}) for w in workers]
    return success(data=data)


@router.get("/workers")
async def list_workers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    service_key: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """师傅列表（分页，可按可接服务类型筛选）"""
    q = db.query(Worker).filter(Worker.is_active == True, Worker.certified == 2)  # noqa: E712
    if service_key:
        sk = f"%{service_key}%"
        q = q.filter(Worker.service_types.like(sk))
    total = q.count()
    workers = q.order_by(Worker.rating.desc(), Worker.service_count.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_worker_to_dict(w) for w in workers],
    }
    return success(data=data)


@router.get("/workers/{worker_id}")
async def get_worker_detail(worker_id: int, db: Session = Depends(get_db)):
    """师傅详情"""
    w = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.is_active == True,
        Worker.certified == 2,
    ).first()  # noqa: E712
    if not w:
        raise HTTPException(status_code=404, detail="师傅不存在或已下架")
    return success(data=_worker_to_dict(w))


@router.get("/{key_or_id}")
async def get_service(key_or_id: str, db: Session = Depends(get_db)):
    """获取服务详情（自动判断是数字 id 还是字符串 key）"""
    svc = service_service.get_service_detail(db, key_or_id)
    if not svc:
        raise HTTPException(status_code=404, detail="服务类型不存在")
    data = _service_to_detail_dict(svc)
    return success(data=data)


# ============================= 管理端接口 =============================


@router.post("")
async def create_service(
    req: ServiceTypeCreateRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_operator),
):
    """创建服务类型（管理后台）"""
    svc = service_service.create_service(db, req.model_dump())
    admin_service.add_admin_audit(
        db, admin.id, "service.create", "service_type", svc.id, commit=True
    )
    data = _service_to_detail_dict(svc)
    return success(data=data, message="创建成功")


@router.put("/{svc_id}")
async def update_service(
    svc_id: int,
    req: ServiceTypeCreateRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_operator),
):
    """更新服务类型（管理后台）"""
    svc = service_service.update_service(db, svc_id, req.model_dump())
    admin_service.add_admin_audit(
        db, admin.id, "service.update", "service_type", svc.id, commit=True
    )
    data = _service_to_detail_dict(svc)
    return success(data=data, message="更新成功")


@router.put("/{svc_id}/active")
async def toggle_active(
    svc_id: int,
    body: ToggleServiceActiveRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_operator),
):
    """切换服务启用状态"""
    svc = service_service.toggle_active(db, svc_id, body.is_active)
    admin_service.add_admin_audit(
        db,
        admin.id,
        "service.active.update",
        "service_type",
        svc.id,
        {"is_active": svc.is_active},
        commit=True,
    )
    return success(data={"id": svc.id, "is_active": svc.is_active}, message="状态更新成功")


@router.post("/seed-default")
async def seed_default_services(
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """一键初始化 8 类标准服务种子数据（开发用）"""
    count = service_service.seed_default_services(db)
    return success(data={"inserted": count}, message=f"已插入 {count} 条服务类型数据")
