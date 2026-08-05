"""内容页/FAQ/协议相关路由"""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_admin, require_admin_operator, require_super_admin
from app.services import content_service
from app.schemas.content import PageUpdateRequest
from app.utils.response import success

router = APIRouter(prefix="/api", tags=["内容页/FAQ"])


@router.get("/faqs")
async def get_faqs(db: Session = Depends(get_db)):
    """获取全部分类+FAQ 列表"""
    data = content_service.list_faqs(db)
    return success(data=data)


def _page_response(page_dict: dict):
    return page_dict


@router.get("/pages/agreement")
async def get_agreement_page(db: Session = Depends(get_db)):
    """获取用户协议页"""
    data = content_service.get_page(db, "agreement")
    return success(data=_page_response(data))


@router.get("/pages/privacy")
async def get_privacy_page(db: Session = Depends(get_db)):
    """获取隐私政策页"""
    data = content_service.get_page(db, "privacy")
    return success(data=_page_response(data))


@router.get("/pages/about")
async def get_about_page(db: Session = Depends(get_db)):
    """获取关于我们页"""
    data = content_service.get_page(db, "about")
    return success(data=_page_response(data))


@router.get("/pages/help")
async def get_help_page(db: Session = Depends(get_db)):
    """获取帮助中心页"""
    data = content_service.get_page(db, "help")
    return success(data=_page_response(data))


@router.get("/pages/{key}")
async def get_page_by_key(
    key: str = Path(..., min_length=1, max_length=64, pattern="^[a-z0-9_-]+$"),
    db: Session = Depends(get_db),
):
    """通用获取任意 key 的页面内容"""
    data = content_service.get_page(db, key)
    return success(data=_page_response(data))


@router.put("/admin/pages/{key}")
async def update_page(
    body: PageUpdateRequest,
    key: str = Path(..., min_length=1, max_length=64, pattern="^[a-z0-9_-]+$"),
    db: Session = Depends(get_db),
    admin=Depends(require_admin_operator),
):
    """管理员：创建或更新页面内容"""
    page = content_service.upsert_page(db, key, body.title, body.content)
    return success(
        data={
            "key": page.key,
            "title": page.title,
            "content": page.content,
            "updated_at": page.updated_at,
        },
        message="页面内容已更新",
    )


@router.post("/admin/pages/seed-default")
async def seed_default_contents(
    admin=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """一键初始化默认页面+FAQ种子数据（开发用）"""
    if settings.is_deployed:
        raise HTTPException(status_code=404, detail="接口不存在")
    pages_count = content_service.seed_default_pages(db)
    faq_count = content_service.seed_default_faqs(db)
    return success(
        data={"pages_inserted": pages_count, "faqs_inserted": faq_count},
        message=f"已插入 {pages_count} 个页面、{faq_count} 条 FAQ",
    )
