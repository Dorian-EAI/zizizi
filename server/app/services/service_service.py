"""服务类型业务逻辑"""

import json
from typing import List, Optional, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.service import ServiceType
from app.schemas.service import ServiceTypeCreateRequest


DEFAULT_SERVICES = [
    {"key": "electric", "name": "水电维修", "category": "居家维修", "price_min": 50, "price_max": 300, "price_unit": "次",
     "description": "专业水电维修服务，包含水龙头、灯具、开关、插座、水管等维修安装。持证电工操作，安全可靠。",
     "process_steps": [
         {"step": 1, "title": "在线预约", "desc": "选择服务类型，填写地址和预约时间"},
         {"step": 2, "title": "师傅接单", "desc": "附近专业师傅快速响应，确认上门时间"},
         {"step": 3, "title": "上门检测", "desc": "师傅上门检查问题，给出维修方案和报价"},
         {"step": 4, "title": "维修施工", "desc": "确认方案后专业施工，确保质量"},
         {"step": 5, "title": "验收付款", "desc": "用户验收满意后付款，享质保服务"},
     ],
     "faq": [
         {"q": "维修需要多长时间？", "a": "简单问题30分钟内可解决，复杂问题根据实际情况而定，师傅会提前告知预计时长。"},
         {"q": "维修后有保修吗？", "a": "所有维修服务均提供30-90天质保（根据项目不同），质保期内出现同样问题免费返修。"},
         {"q": "师傅上门检查后不修需要付费吗？", "a": "上门检测费30-50元，如果选择我们维修则检测费可抵扣维修费。"},
     ],
     "sort_order": 1},
    {"key": "air_condition", "name": "空调维修", "category": "家电维修", "price_min": 80, "price_max": 500, "price_unit": "次",
     "description": "空调维修、清洗、加氟、安装移机一条龙服务。专业师傅持证上岗，熟悉各品牌空调。",
     "process_steps": [
         {"step": 1, "title": "在线预约", "desc": "选择空调服务类型"},
         {"step": 2, "title": "师傅上门", "desc": "空调技师准时上门"},
         {"step": 3, "title": "检测报价", "desc": "检测故障并告知费用"},
         {"step": 4, "title": "专业维修", "desc": "使用原厂配件维修"},
         {"step": 5, "title": "测试验收", "desc": "开机测试制冷/制热效果"},
     ],
     "faq": [
         {"q": "空调多久需要清洗一次？", "a": "建议家用空调每半年深度清洗一次，使用频繁的夏季前后各清洗一次最佳。"},
         {"q": "空调不制冷是什么原因？", "a": "常见原因包括：缺氟、滤网堵塞、压缩机故障、温控器问题等，需师傅上门检测确定。"},
     ],
     "sort_order": 2},
    {"key": "appliance", "name": "家电维修", "category": "家电维修", "price_min": 60, "price_max": 400, "price_unit": "次",
     "description": "冰箱、洗衣机、热水器、油烟机、燃气灶、微波炉等各类家电维修服务。",
     "sort_order": 3},
    {"key": "plumbing", "name": "管道疏通", "category": "居家维修", "price_min": 80, "price_max": 300, "price_unit": "次",
     "description": "马桶、地漏、下水道、洗菜池、浴缸等各类管道疏通，高压清洗。",
     "sort_order": 4},
    {"key": "door_window", "name": "门窗维修", "category": "居家维修", "price_min": 50, "price_max": 300, "price_unit": "次",
     "description": "木门、防盗门、铝合金门窗、纱窗、玻璃、合页、门锁维修更换。",
     "sort_order": 5},
    {"key": "circuit", "name": "电路检修", "category": "居家维修", "price_min": 100, "price_max": 500, "price_unit": "次",
     "description": "跳闸、漏电、短路、线路老化检修，电路改造，持证电工安全操作。",
     "sort_order": 6},
    {"key": "furniture", "name": "家具安装", "category": "安装服务", "price_min": 50, "price_max": 300, "price_unit": "次",
     "description": "网购家具、衣柜、鞋柜、床、办公桌椅等家具安装组装服务。",
     "sort_order": 7},
    {"key": "wall_repair", "name": "墙面修补", "category": "翻新维修", "price_min": 100, "price_max": 500, "price_unit": "次",
     "description": "墙面裂缝、孔洞、渗水、发霉修补，局部刷漆翻新。",
     "sort_order": 8},
]


def list_active_services(db: Session) -> List[ServiceType]:
    """获取激活的服务类型列表，按 sort_order 升序"""
    return (
        db.query(ServiceType)
        .filter(ServiceType.is_active == True)
        .order_by(ServiceType.sort_order.asc())
        .limit(500)
        .all()
    )


def get_service_detail(db: Session, key_or_id: Union[str, int]) -> ServiceType:
    """根据 key 或 id 获取服务详情"""
    q = db.query(ServiceType)
    if isinstance(key_or_id, int) or (isinstance(key_or_id, str) and key_or_id.isdigit()):
        svc = q.filter(ServiceType.id == int(key_or_id)).first()
    else:
        svc = q.filter(ServiceType.key == key_or_id).first()
    if not svc:
        raise HTTPException(status_code=404, detail="服务类型不存在")
    return svc


def create_service(db: Session, data: dict) -> ServiceType:
    """创建服务类型"""
    existing = db.query(ServiceType).filter(ServiceType.key == data.get("key")).first()
    if existing:
        raise HTTPException(status_code=400, detail="服务 key 已存在")

    process_steps = data.get("process_steps")
    faq = data.get("faq")
    cases = data.get("cases")
    service_images = data.get("service_images")
    detail_sections = data.get("detail_sections")
    service_standards = data.get("service_standards")
    price_details = data.get("price_details")

    svc = ServiceType(
        key=data["key"],
        name=data["name"],
        icon=data.get("icon"),
        banner=data.get("banner"),
        category=data.get("category"),
        price_min=data.get("price_min", 0),
        price_max=data.get("price_max", 0),
        price_unit=data.get("price_unit", "次"),
        description=data.get("description"),
        process_steps=json.dumps(process_steps, ensure_ascii=False) if process_steps else None,
        faq=json.dumps(faq, ensure_ascii=False) if faq else None,
        cases=json.dumps(cases, ensure_ascii=False) if cases else None,
        intro_video=data.get("intro_video"),
        service_images=json.dumps(service_images, ensure_ascii=False) if service_images else None,
        detail_sections=json.dumps(detail_sections, ensure_ascii=False) if detail_sections else None,
        service_standards=json.dumps(service_standards, ensure_ascii=False) if service_standards else None,
        price_details=json.dumps(price_details, ensure_ascii=False) if price_details else None,
        sort_order=data.get("sort_order", 0),
        is_active=True,
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


def update_service(db: Session, svc_id: int, data: dict) -> ServiceType:
    """更新服务类型"""
    svc = db.query(ServiceType).filter(ServiceType.id == svc_id).first()
    if not svc:
        raise HTTPException(status_code=404, detail="服务类型不存在")

    updatable = ["name", "icon", "banner", "category", "price_min", "price_max",
                 "price_unit", "description", "sort_order", "is_active", "intro_video"]
    for k in updatable:
        if k in data:
            setattr(svc, k, data[k])

    if "process_steps" in data:
        svc.process_steps = json.dumps(data["process_steps"], ensure_ascii=False) if data["process_steps"] else None
    if "faq" in data:
        svc.faq = json.dumps(data["faq"], ensure_ascii=False) if data["faq"] else None
    if "cases" in data:
        svc.cases = json.dumps(data["cases"], ensure_ascii=False) if data["cases"] else None
    if "service_images" in data:
        svc.service_images = json.dumps(data["service_images"], ensure_ascii=False) if data["service_images"] else None
    if "detail_sections" in data:
        svc.detail_sections = json.dumps(data["detail_sections"], ensure_ascii=False) if data["detail_sections"] else None
    if "service_standards" in data:
        svc.service_standards = json.dumps(data["service_standards"], ensure_ascii=False) if data["service_standards"] else None
    if "price_details" in data:
        svc.price_details = json.dumps(data["price_details"], ensure_ascii=False) if data["price_details"] else None

    db.commit()
    db.refresh(svc)
    return svc


def toggle_active(db: Session, svc_id: int, is_active: bool) -> ServiceType:
    """切换服务启用状态"""
    svc = db.query(ServiceType).filter(ServiceType.id == svc_id).first()
    if not svc:
        raise HTTPException(status_code=404, detail="服务类型不存在")
    svc.is_active = is_active
    db.commit()
    db.refresh(svc)
    return svc


def seed_default_services(db: Session) -> int:
    """初始化 8 类标准服务种子数据"""
    count = 0
    for svc_data in DEFAULT_SERVICES:
        existing = db.query(ServiceType).filter(ServiceType.key == svc_data["key"]).first()
        if existing:
            continue
        process_steps = svc_data.get("process_steps")
        faq = svc_data.get("faq")
        cases = svc_data.get("cases")
        svc = ServiceType(
            key=svc_data["key"],
            name=svc_data["name"],
            category=svc_data.get("category"),
            price_min=svc_data.get("price_min", 0),
            price_max=svc_data.get("price_max", 0),
            price_unit=svc_data.get("price_unit", "次"),
            description=svc_data.get("description"),
            process_steps=json.dumps(process_steps, ensure_ascii=False) if process_steps else None,
            faq=json.dumps(faq, ensure_ascii=False) if faq else None,
            cases=json.dumps(cases, ensure_ascii=False) if cases else None,
            sort_order=svc_data.get("sort_order", 0),
            is_active=True,
        )
        db.add(svc)
        count += 1
    db.commit()
    return count
