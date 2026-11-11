"""文件上传相关 Pydantic 模型"""

from pydantic import BaseModel, Field


class UploadFileResponse(BaseModel):
    url: str = Field(..., max_length=512)
    size: int
    filename: str = Field(..., max_length=256)


class UploadPolicyResponse(BaseModel):
    access_id: str = Field(..., max_length=256)
    policy: str = Field(..., max_length=4096)
    signature: str = Field(..., max_length=512)
    dir: str = Field(..., max_length=256)
    host: str = Field(..., max_length=512)
    expire_seconds: int
    provider: str = Field("local", max_length=32)
    cdn_domain: str = Field("", max_length=512)
