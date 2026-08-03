"""用户相关 Pydantic 模型"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_REAL_NAME_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z·•\- ]{2,32}$")
_ID_CARD_RE = re.compile(r"^\d{17}[\dX]$")
_IMAGE_REF_RE = re.compile(r"^(?:https?://[^\s]+|/uploads/[^\s]+)$", re.IGNORECASE)
_ID_CARD_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CARD_CHECK_CODES = "10X98765432"


def _validate_phone(v: Optional[str]) -> Optional[str]:
    """校验中国大陆 11 位手机号格式"""
    if v is None:
        return v
    if not _PHONE_RE.match(v):
        raise ValueError("无效的手机号格式")
    return v


# ===== 请求 =====
class WxLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., max_length=256)
    nickname: Optional[str] = Field(None, max_length=32)
    avatar: Optional[str] = Field(None, max_length=512)


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: Optional[str] = Field(None, max_length=32)
    avatar: Optional[str] = Field(None, max_length=512)
    phone: Optional[str] = Field(None, max_length=11)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)


class BindPhoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(..., max_length=11)
    verification_code: str = Field(..., min_length=4, max_length=8)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)  # type: ignore[return-value]


class SwitchRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "worker"]


class WorkerCertificationRequest(BaseModel):
    """师傅认证申请。

    身份证使用 SecretStr，业务层读取后立即加密；任何响应模型都不得包含该字段。
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    real_name: str = Field(..., min_length=2, max_length=32)
    phone: str = Field(..., max_length=11)
    phone_verification_code: SecretStr = Field(..., min_length=4, max_length=8)
    id_card: SecretStr
    id_front: str = Field(..., max_length=512)
    id_back: str = Field(..., max_length=512)
    certificate_images: list[str] = Field(default_factory=list, max_length=4)
    health_certificate: Optional[str] = Field(None, max_length=512)
    service_city: str = Field(..., min_length=2, max_length=32)
    service_districts: list[str] = Field(..., min_length=1, max_length=10)
    service_types: list[str] = Field(..., min_length=1, max_length=20)
    price_min: Decimal = Field(..., gt=0, le=1000000, decimal_places=2)
    price_max: Decimal = Field(..., gt=0, le=1000000, decimal_places=2)

    @field_validator("real_name")
    @classmethod
    def validate_real_name(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value.strip())
        if not _REAL_NAME_RE.fullmatch(normalized):
            raise ValueError("姓名格式无效")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_certification_phone(cls, value: str) -> str:
        return _validate_phone(value)  # type: ignore[return-value]

    @field_validator("phone_verification_code")
    @classmethod
    def validate_phone_verification_code(cls, value: SecretStr) -> SecretStr:
        plain = value.get_secret_value().strip()
        if not plain.isdigit():
            raise ValueError("短信验证码格式无效")
        return SecretStr(plain)

    @field_validator("id_card")
    @classmethod
    def validate_id_card(cls, value: SecretStr) -> SecretStr:
        plain = value.get_secret_value().strip().upper()
        if not _ID_CARD_RE.fullmatch(plain):
            raise ValueError("身份证号格式无效")
        try:
            birthday = datetime.strptime(plain[6:14], "%Y%m%d").date()
        except ValueError as error:
            raise ValueError("身份证号格式无效") from error
        if birthday.year < 1900 or birthday > datetime.utcnow().date():
            raise ValueError("身份证号格式无效")
        checksum = sum(int(char) * weight for char, weight in zip(plain[:17], _ID_CARD_WEIGHTS))
        if plain[-1] != _ID_CARD_CHECK_CODES[checksum % 11]:
            raise ValueError("身份证号格式无效")
        return SecretStr(plain)

    @field_validator("id_front", "id_back", "health_certificate")
    @classmethod
    def validate_image_ref(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not _IMAGE_REF_RE.fullmatch(value):
            raise ValueError("图片地址无效")
        return value

    @field_validator("certificate_images")
    @classmethod
    def validate_certificate_images(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            value = value.strip()
            if len(value) > 512 or not _IMAGE_REF_RE.fullmatch(value):
                raise ValueError("图片地址无效")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @field_validator("service_districts", "service_types")
    @classmethod
    def validate_non_empty_items(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            value = re.sub(r"\s+", " ", value.strip())
            if not value or len(value) > 32:
                raise ValueError("服务区域或项目无效")
            if value not in normalized:
                normalized.append(value)
        if not normalized:
            raise ValueError("服务区域或项目不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.price_max < self.price_min:
            raise ValueError("最高报价不得低于最低报价")
        return self


class AddressCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=32)
    phone: str = Field(..., max_length=11)
    province: str = Field(..., max_length=256)
    city: str = Field(..., max_length=256)
    district: str = Field(..., max_length=256)
    detail: str = Field(..., max_length=512)
    label: Optional[str] = Field("家", max_length=256)
    is_default: bool = False
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)  # type: ignore[return-value]


class AddressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, max_length=32)
    phone: Optional[str] = Field(None, max_length=11)
    province: Optional[str] = Field(None, max_length=256)
    city: Optional[str] = Field(None, max_length=256)
    district: Optional[str] = Field(None, max_length=256)
    detail: Optional[str] = Field(None, max_length=512)
    label: Optional[str] = Field(None, max_length=256)
    is_default: Optional[bool] = None
    location_lat: Optional[float] = Field(None, ge=-90, le=90)
    location_lng: Optional[float] = Field(None, ge=-180, le=180)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)


# ===== 响应 =====
class LoginResponse(BaseModel):
    token: str = Field(..., max_length=256)
    user_id: int
    role: str = Field(..., max_length=32)
    is_new: bool


class UserInfoResponse(BaseModel):
    id: int
    nickname: Optional[str] = Field(None, max_length=32)
    avatar: Optional[str] = Field(None, max_length=512)
    phone: Optional[str] = Field(None, max_length=11)
    role: str = Field(..., max_length=32)
    member_level: int
    growth_value: int
    balance: float


class WorkerInfoResponse(BaseModel):
    id: int
    nickname: Optional[str] = Field(None, max_length=32)
    avatar: Optional[str] = Field(None, max_length=512)
    phone: Optional[str] = Field(None, max_length=11)
    real_name: Optional[str] = Field(None, max_length=32)
    certified: int
    skills: Optional[str] = Field(None, max_length=256)
    rating: float
    service_count: int
    level: int
    balance: float
    is_online: bool


class AddressResponse(BaseModel):
    id: int
    name: str = Field(..., max_length=32)
    phone: str = Field(..., max_length=11)
    province: str = Field(..., max_length=256)
    city: str = Field(..., max_length=256)
    district: str = Field(..., max_length=256)
    detail: str = Field(..., max_length=512)
    label: str = Field(..., max_length=256)
    is_default: bool
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None

    class Config:
        from_attributes = True
