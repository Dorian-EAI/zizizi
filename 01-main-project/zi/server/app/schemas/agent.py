"""AI 下单 Agent 请求模型"""

from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# 约 3 MiB 原图的 base64 上限（与服务端解码校验保持一致）
_Base64Image = Annotated[str, Field(max_length=4_500_000)]


class AgentTurnRequest(BaseModel):
    """一轮对话请求

    - message：用户文字，可为空（仅发照片）
    - image_urls：客户端已上传的图片 URL（随订单归档）
    - image_base64_list：照片 base64，服务端负责校验、落库并用于视觉理解
    - action：confirm=确认下单；cancel=取消当前草稿；reset=开启新对话
    """

    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = Field(None, max_length=64)
    message: str = Field("", max_length=1000)
    image_urls: List[str] = Field(default_factory=list, max_length=9)
    image_base64_list: List[_Base64Image] = Field(default_factory=list, max_length=9)
    action: Optional[Literal["confirm", "cancel", "reset"]] = None
    confirm_token: Optional[str] = Field(None, max_length=64)

    @model_validator(mode="after")
    def require_content(self):
        if (
            not self.message.strip()
            and not self.image_urls
            and not self.image_base64_list
            and self.action is None
        ):
            raise ValueError("请输入问题或上传照片")
        return self
