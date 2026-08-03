"""文件上传相关路由"""

from typing import Optional, List

from fastapi import APIRouter, Depends, UploadFile, File, Query, Request, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_current_account, get_current_admin
from app.models.admin import Admin
from app.schemas.upload import UploadFileResponse, UploadPolicyResponse
from app.services import upload_service
from app.utils.response import success
from app.utils.rate_limit import limiter, LIMIT_UPLOAD_SINGLE, LIMIT_UPLOAD_BATCH
from app.config import settings

router = APIRouter(prefix="/api/upload", tags=["文件上传"])


async def _read_upload_limited(file: UploadFile, max_mb: int) -> bytes:
    """分块读取并在超过上限时立即终止，避免无界内存占用。"""
    max_bytes = max_mb * 1024 * 1024
    data = bytearray()
    while True:
        chunk = await file.read(min(1024 * 1024, max_bytes + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(status_code=413, detail=f"文件大小超过上限 {max_mb}MB")
    return bytes(data)


class DeleteFileRequest(BaseModel):
    url: str = Field(..., max_length=512)


@router.post("/image")
@limiter.limit(LIMIT_UPLOAD_SINGLE)
async def upload_image(
    request: Request,
    category: str = Query("images", max_length=32, description="分类: images/certificate 等"),
    file: UploadFile = File(...),
    account: tuple = Depends(get_current_account),
):
    """上传单张图片，返回 url/size/filename。

    根据 OSS_PROVIDER 优先走阿里云 OSS 或腾讯云 COS，未配置/失败则降级本地存储。
    """
    category = upload_service.normalize_category(category)
    if category == "certificate" and account[1] != "worker":
        raise HTTPException(status_code=403, detail="仅师傅账号可上传认证材料")
    max_mb = 20 if category == "certificate" else 10
    file_bytes = await _read_upload_limited(file, max_mb)
    result = upload_service.upload_image(category, file_bytes, file.filename or "")
    data = UploadFileResponse(**result).model_dump()
    return success(data=data, message="上传成功")


@router.post("/images")
@limiter.limit(LIMIT_UPLOAD_BATCH)
async def upload_images(
    request: Request,
    category: str = Query("images", max_length=32, description="分类: images/certificate 等"),
    files: List[UploadFile] = File(..., description="最多 9 张"),
    account: tuple = Depends(get_current_account),
):
    """批量上传图片（最多 9 张）。按 OSS_PROVIDER 优先走云存储，失败降级本地。"""
    if len(files) > 9:
        from app.utils.response import error_response
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"code": -1, "message": "最多支持同时上传 9 张图片", "data": None},
        )

    category = upload_service.normalize_category(category)
    if category == "certificate" and account[1] != "worker":
        raise HTTPException(status_code=403, detail="仅师傅账号可上传认证材料")
    max_mb = 20 if category == "certificate" else 10
    results: list = []
    for f in files:
        file_bytes = await _read_upload_limited(f, max_mb)
        res = upload_service.upload_image(category, file_bytes, f.filename or "")
        results.append(UploadFileResponse(**res).model_dump())
    return success(data=results, message="上传成功")


@router.delete("/file")
async def delete_file(
    req: DeleteFileRequest,
    admin: Admin = Depends(get_current_admin),
):
    """管理员删除本地上传文件。普通账号不能按可猜测 URL 删除他人文件。"""
    ok = upload_service.delete_file_by_url(req.url)
    return success(data={"deleted": ok}, message="删除成功" if ok else "文件不存在")


@router.get("/oss-policy")
async def get_oss_policy(
    category: str = Query("images", max_length=32, description="分类目录前缀，默认 images"),
    account: tuple = Depends(get_current_account),
):
    """仅供本地联调的直传签名。

    直传无法复用服务端的大小、魔数与认证材料权限校验，因此体验版和生产版
    一律关闭；正式客户端使用 ``/image`` 或 ``/images`` 的受检上传链路。
    """
    if settings.is_deployed:
        raise HTTPException(status_code=404, detail="直传接口在当前环境不可用")
    if category == "certificate" and account[1] != "worker":
        raise HTTPException(status_code=403, detail="仅师傅账号可上传认证材料")
    data = upload_service.sign_oss_upload(category)
    resp = UploadPolicyResponse(**data).model_dump()
    return success(data=resp)
