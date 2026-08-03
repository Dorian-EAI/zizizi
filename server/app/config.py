"""全局配置管理 — 基于 pydantic-settings，从环境变量读取

安全说明：
- APP_DEBUG 默认 False，开发时显式设为 true
- staging/production 启动时强制执行同一套安全配置校验
- ADMIN_DEFAULT_PASSWORD 仅用于首次启动 init_db.seed_admin 写入默认账号，
  之后必须通过管理后台修改密码；本字段不再用于运行时登录后门
- CORS_ORIGINS 必须是逗号分隔的显式白名单；"*" 仅在 APP_DEBUG=true 时允许
"""

import base64
import ipaddress
import re
import secrets
from pathlib import Path
from urllib.parse import quote_plus, urlsplit
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional, List


# 占位符常量 — 启动时若 JWT_SECRET_KEY 仍为此值且处于生产环境则拒绝启动
JWT_SECRET_PLACEHOLDER = "change-this-to-a-random-secret-key"
ADMIN_PASSWORD_PLACEHOLDER = "admin123"
SERVER_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "自家人居家维修后端"
    APP_ENV: str = "development"  # development | staging | production
    APP_DEBUG: bool = False  # 默认关闭，开发时显式开启
    # 内置后台依赖第三方 CDN 且使用浏览器存储 token，仅限本地开发。
    ENABLE_BUILTIN_ADMIN: bool = True

    # 数据库 — MySQL（默认）或 SQLite（开发测试自动降级）
    DB_DRIVER: str = "mysql"          # mysql | sqlite
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "zjr_repair"
    SQLITE_PATH: str = "./zjr_repair.db"  # SQLite 文件路径

    # JWT
    JWT_SECRET_KEY: str = JWT_SECRET_PLACEHOLDER
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 168  # 7 天（建议生产配合短期 token + refresh）
    ADMIN_JWT_EXPIRE_MINUTES: int = 60

    # 微信小程序（仅非生产环境允许留空并使用 mock 登录）
    WX_APPID: str = ""
    WX_SECRET: str = ""

    # 微信订阅消息模板 ID（未配置时只保留站内消息，不伪造推送成功）
    WX_TEMPLATE_ORDER_BIDDING: str = ""
    WX_TEMPLATE_ORDER_ACCEPTED: str = ""
    WX_TEMPLATE_SERVICE_FINISHED: str = ""
    WX_TEMPLATE_PAYMENT_SUCCESS_USER: str = ""
    WX_TEMPLATE_PAYMENT_SUCCESS_WORKER: str = ""
    WX_TEMPLATE_WITHDRAW_SUCCESS: str = ""
    WX_TEMPLATE_COUPON_EXPIRE: str = ""

    # 微信支付 API v3
    # 本地开发可显式启用 mock；staging/production 必须关闭并配置真实商户凭据。
    WX_PAY_MOCK_ENABLED: bool = True
    WX_PAY_MOCK_CALLBACK_SECRET: str = ""
    WX_MCH_ID: str = ""
    WX_API_V3_KEY: str = ""
    # 可填写 PEM 正文（环境变量中的 \n 会被还原）或 PEM 文件绝对路径。
    WX_MERCHANT_PRIVATE_KEY: str = ""
    WX_MERCHANT_SERIAL_NO: str = ""
    # SDK 用于缓存/读取微信支付平台证书的目录。
    WX_PLATFORM_CERT_DIR: str = ""
    WX_PAY_NOTIFY_URL: str = ""
    WX_REFUND_NOTIFY_URL: str = ""
    WX_PAY_TIMEOUT_SECONDS: int = 15
    # 待支付单超过此时间才允许查单并尝试关单；关单成功/终态失败后释放余额预留。
    WX_PAYMENT_PENDING_TIMEOUT_MINUTES: int = 30
    WX_RECONCILE_BATCH_SIZE: int = 100
    WX_REFUND_RETRY_INTERVAL_MINUTES: int = 5
    WX_REFUND_MAX_RETRIES: int = 5

    # AI 大模型（mock = 纯代码模拟，免费用）
    AI_PROVIDER: str = "mock"
    AI_API_KEY: str = ""
    AI_API_BASE: str = "https://ark.cn-beijing.volces.com/api/v3"

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    UPLOAD_URL_PREFIX: str = "/uploads"
    # OSS 对象存储（留空 = 走本地开发存储）
    OSS_PROVIDER: str = "local"  # local | aliyun | tencent
    OSS_ACCESS_KEY: str = ""
    OSS_SECRET_KEY: str = ""
    OSS_BUCKET: str = ""
    OSS_ENDPOINT: str = "https://oss-cn-shenzhen.aliyuncs.com"
    OSS_REGION: str = ""
    OSS_CDN_DOMAIN: str = ""

    # 腾讯云 COS
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_BUCKET: str = ""
    COS_REGION: str = ""
    COS_CDN_DOMAIN: str = ""

    # Redis（留空/未安装则优雅降级）
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    RATE_LIMIT_STORAGE: str = ""
    RATE_LIMIT_REDIS_DB: int = 1
    # 仅当应用只允许受信反向代理访问时开启，避免客户端伪造 X-Forwarded-For。
    TRUST_PROXY_HEADERS: bool = False
    TRUSTED_PROXY_CIDRS: str = ""
    SCHEDULER_ENABLED: bool = True

    # 短信服务（mock = 控制台打印，aliyun = 阿里云 dysmsapi，tencent = 腾讯云 SMS）
    SMS_PROVIDER: str = "mock"  # mock | aliyun | tencent
    SMS_ACCESS_KEY: str = ""
    SMS_SECRET_KEY: str = ""
    SMS_TENCENT_APP_ID: str = ""
    SMS_TENCENT_REGION: str = "ap-guangzhou"
    SMS_SIGN_NAME: str = "自家人维修"
    SMS_TEMPLATE_ORDER_PENDING: str = ""
    SMS_TEMPLATE_ORDER_COMPLETED: str = ""
    SMS_TEMPLATE_ORDER_PAID: str = ""
    SMS_TEMPLATE_WITHDRAW: str = ""
    SMS_TEMPLATE_VERIFY_CODE: str = ""

    # 运营后台默认账号（仅首次 init_db 写入；运行时不再用作登录后门）
    ADMIN_DEFAULT_USER: str = "admin"
    ADMIN_DEFAULT_PASSWORD: str = ADMIN_PASSWORD_PLACEHOLDER

    # 地图服务（留空 = 使用 Haversine 直线距离模式）
    MAP_PROVIDER: str = "local"  # local | amap | tencent
    AMAP_API_KEY: str = ""       # 高德 Web 服务 Key
    TENCENT_MAP_KEY: str = ""   # 腾讯位置服务 Key

    # ===== 安全相关 =====
    # CORS 允许的源，逗号分隔；"*" 仅在 APP_DEBUG=true 时允许
    CORS_ORIGINS: str = ""  # 例: https://m.example.com,https://admin.example.com
    # TrustedHost 白名单，逗号分隔；为空时开发模式允许所有，生产必须显式配置
    ALLOWED_HOSTS: str = ""  # 例: api.example.com,localhost

    # 敏感字段加密主密钥（AES，用于身份证号等 PII 字段；
    # 必须为 32 字节 base64 字符串；为空时启动自动生成临时密钥，重启后已加密数据无法解密）
    FIELD_ENC_KEY: str = ""

    @field_validator(
        "APP_ENV",
        "DB_DRIVER",
        "SMS_PROVIDER",
        "AI_PROVIDER",
        "OSS_PROVIDER",
        "MAP_PROVIDER",
        mode="before",
    )
    @classmethod
    def normalize_enum_setting(cls, value):
        """枚举配置入模即标准化，避免门禁与运行时读取不同值。"""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("JWT_ALGORITHM", mode="before")
    @classmethod
    def normalize_jwt_algorithm(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @property
    def database_url(self) -> str:
        if self.DB_DRIVER == "sqlite":
            if self.SQLITE_PATH == ":memory:":
                return "sqlite:///:memory:"
            sqlite_path = Path(self.SQLITE_PATH).expanduser()
            if not sqlite_path.is_absolute():
                sqlite_path = SERVER_ROOT / sqlite_path
            return f"sqlite:///{sqlite_path.resolve()}"
        # MySQL
        user = quote_plus(self.DB_USER or "")
        password = quote_plus(self.DB_PASSWORD or "")
        database = quote_plus(self.DB_NAME or "")
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{database}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> List[str]:
        """解析 CORS_ORIGINS 为列表"""
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_hosts_list(self) -> List[str]:
        """解析 ALLOWED_HOSTS 为列表"""
        if not self.ALLOWED_HOSTS:
            return []
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def trusted_proxy_cidr_list(self) -> List[str]:
        if not self.TRUSTED_PROXY_CIDRS:
            return []
        return [item.strip() for item in self.TRUSTED_PROXY_CIDRS.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() == "production"

    @property
    def is_deployed(self) -> bool:
        """体验/正式环境均不得使用开发降级。"""
        return self.APP_ENV.strip().lower() in {"staging", "production"}

    def validate_security(self) -> None:
        """启动时安全配置校验

        体验/生产环境（APP_ENV=staging/production）下：
        - JWT_SECRET_KEY 不得为默认占位符
        - ADMIN_DEFAULT_PASSWORD 不得为默认 admin123
        - APP_DEBUG 必须为 False
        - 必须配置 CORS_ORIGINS 显式白名单（不得为 "*" 或空）
        - 必须配置 ALLOWED_HOSTS

        违反任意一条直接抛 RuntimeError 拒绝启动。
        """
        app_env = self.APP_ENV.strip().lower()
        if app_env not in {"development", "testing", "staging", "production"}:
            raise RuntimeError(
                "APP_ENV 仅允许 development/testing/staging/production，"
                "拒绝把未知环境按开发模式运行"
            )
        if self.DB_DRIVER.strip().lower() not in {"mysql", "sqlite"}:
            raise RuntimeError("DB_DRIVER 仅允许 mysql/sqlite")
        if not self.is_deployed:
            return

        errors = []
        if self.DB_DRIVER.strip().lower() != "mysql":
            errors.append("DB_DRIVER 在生产环境必须为 mysql")
        if not self.DB_PASSWORD:
            errors.append("DB_PASSWORD 在生产环境不得为空")
        if self.JWT_SECRET_KEY == JWT_SECRET_PLACEHOLDER:
            errors.append("JWT_SECRET_KEY 仍为默认占位符，请生成随机密钥")
        if len(self.JWT_SECRET_KEY) < 32:
            errors.append("JWT_SECRET_KEY 长度不足 32 字符")
        if self.JWT_ALGORITHM.upper() not in {"HS256", "HS384", "HS512"}:
            errors.append("JWT_ALGORITHM 仅允许 HS256/HS384/HS512")
        if not 1 <= self.JWT_EXPIRE_HOURS <= 24:
            errors.append("JWT_EXPIRE_HOURS 在生产环境必须为 1 到 24 小时")
        if not 5 <= self.ADMIN_JWT_EXPIRE_MINUTES <= 1440:
            errors.append("ADMIN_JWT_EXPIRE_MINUTES 必须为 5 到 1440 分钟")
        if self.ADMIN_DEFAULT_PASSWORD == ADMIN_PASSWORD_PLACEHOLDER:
            errors.append("ADMIN_DEFAULT_PASSWORD 仍为默认 admin123")
        if len(self.ADMIN_DEFAULT_PASSWORD) < 12:
            errors.append("ADMIN_DEFAULT_PASSWORD 生产环境至少 12 个字符")
        if self.APP_DEBUG:
            errors.append("APP_DEBUG 在生产环境必须为 false")
        if self.ENABLE_BUILTIN_ADMIN:
            errors.append("ENABLE_BUILTIN_ADMIN 在生产环境必须为 false，请部署独立构建的安全后台")
        if not self.cors_origin_list or "*" in self.cors_origin_list:
            errors.append("CORS_ORIGINS 在生产环境必须为显式白名单，不得为空或 *")
        for origin in self.cors_origin_list:
            try:
                parsed_origin = urlsplit(origin)
                origin_valid = (
                    parsed_origin.scheme == "https"
                    and bool(parsed_origin.hostname)
                    and parsed_origin.username is None
                    and parsed_origin.password is None
                    and parsed_origin.path in ("", "/")
                    and not parsed_origin.query
                    and not parsed_origin.fragment
                    and "*" not in (parsed_origin.hostname or "")
                )
                _ = parsed_origin.port
            except ValueError:
                origin_valid = False
            if not origin_valid:
                errors.append(f"CORS_ORIGINS 含无效或非 HTTPS origin: {origin}")
        if not self.allowed_hosts_list:
            errors.append("ALLOWED_HOSTS 在生产环境必须配置")
        host_pattern = re.compile(
            r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
        )
        for host in self.allowed_hosts_list:
            if "*" in host or "://" in host or "/" in host or ":" in host or not host_pattern.fullmatch(host):
                errors.append(f"ALLOWED_HOSTS 含无效主机名: {host}")
        if not self.FIELD_ENC_KEY:
            errors.append("FIELD_ENC_KEY 在生产环境必须配置（用于 PII 字段加密）")
        else:
            try:
                decoded_field_key = base64.b64decode(self.FIELD_ENC_KEY, validate=True)
            except (ValueError, TypeError):
                decoded_field_key = b""
            if len(decoded_field_key) != 32:
                errors.append("FIELD_ENC_KEY 必须是 32 字节随机值的标准 Base64 编码")
        if self.WX_PAY_MOCK_ENABLED:
            errors.append("WX_PAY_MOCK_ENABLED 在生产环境必须为 false")
        rate_limit_storage = self.RATE_LIMIT_STORAGE.strip().lower()
        if rate_limit_storage and not rate_limit_storage.startswith(("redis://", "rediss://")):
            errors.append("RATE_LIMIT_STORAGE 在生产环境必须使用 redis:// 或 rediss://")
        if not 0 <= self.REDIS_DB <= 15:
            errors.append("REDIS_DB 必须在 0 到 15 之间")
        if not 0 <= self.RATE_LIMIT_REDIS_DB <= 15:
            errors.append("RATE_LIMIT_REDIS_DB 必须在 0 到 15 之间")
        if not rate_limit_storage and self.RATE_LIMIT_REDIS_DB == self.REDIS_DB:
            errors.append("RATE_LIMIT_REDIS_DB 必须与 REDIS_DB 分离")
        if self.TRUST_PROXY_HEADERS:
            if not self.trusted_proxy_cidr_list:
                errors.append("TRUST_PROXY_HEADERS=true 时必须配置 TRUSTED_PROXY_CIDRS")
            for cidr in self.trusted_proxy_cidr_list:
                try:
                    ipaddress.ip_network(cidr, strict=False)
                except ValueError:
                    errors.append(f"TRUSTED_PROXY_CIDRS 含无效网段: {cidr}")

        payment_fields = {
            "WX_APPID": self.WX_APPID,
            "WX_SECRET": self.WX_SECRET,
            "WX_MCH_ID": self.WX_MCH_ID,
            "WX_API_V3_KEY": self.WX_API_V3_KEY,
            "WX_MERCHANT_PRIVATE_KEY": self.WX_MERCHANT_PRIVATE_KEY,
            "WX_MERCHANT_SERIAL_NO": self.WX_MERCHANT_SERIAL_NO,
            "WX_PAY_NOTIFY_URL": self.WX_PAY_NOTIFY_URL,
            "WX_REFUND_NOTIFY_URL": self.WX_REFUND_NOTIFY_URL,
        }
        for field_name, value in payment_fields.items():
            if not value:
                errors.append(f"{field_name} 在生产环境必须配置")
        if self.WX_API_V3_KEY and len(self.WX_API_V3_KEY) != 32:
            errors.append("WX_API_V3_KEY 必须为 32 字符")
        for field_name, value in (
            ("WX_PAY_NOTIFY_URL", self.WX_PAY_NOTIFY_URL),
            ("WX_REFUND_NOTIFY_URL", self.WX_REFUND_NOTIFY_URL),
        ):
            if value and not value.lower().startswith("https://"):
                errors.append(f"{field_name} 在生产环境必须使用 HTTPS")
        if self.WX_PAY_TIMEOUT_SECONDS <= 0:
            errors.append("WX_PAY_TIMEOUT_SECONDS 必须大于 0")
        if self.WX_PAYMENT_PENDING_TIMEOUT_MINUTES <= 0:
            errors.append("WX_PAYMENT_PENDING_TIMEOUT_MINUTES 必须大于 0")
        if not 1 <= self.WX_RECONCILE_BATCH_SIZE <= 1000:
            errors.append("WX_RECONCILE_BATCH_SIZE 必须在 1 到 1000 之间")
        if self.WX_REFUND_RETRY_INTERVAL_MINUTES <= 0:
            errors.append("WX_REFUND_RETRY_INTERVAL_MINUTES 必须大于 0")
        if self.WX_REFUND_MAX_RETRIES <= 0:
            errors.append("WX_REFUND_MAX_RETRIES 必须大于 0")

        sms_provider = self.SMS_PROVIDER.strip().lower()
        if sms_provider not in {"aliyun", "tencent"}:
            errors.append("SMS_PROVIDER 在生产环境必须为 aliyun 或 tencent，禁止 mock/未知 provider")
        else:
            sms_fields = {
                "SMS_ACCESS_KEY": self.SMS_ACCESS_KEY,
                "SMS_SECRET_KEY": self.SMS_SECRET_KEY,
                "SMS_SIGN_NAME": self.SMS_SIGN_NAME,
                "SMS_TEMPLATE_VERIFY_CODE": self.SMS_TEMPLATE_VERIFY_CODE,
            }
            for field_name, value in sms_fields.items():
                if not value:
                    errors.append(f"{field_name} 在生产环境使用真实短信服务时必须配置")
            if sms_provider == "tencent" and not self.SMS_TENCENT_APP_ID:
                errors.append("SMS_TENCENT_APP_ID 在生产环境使用腾讯云短信时必须配置")

        ai_provider = self.AI_PROVIDER.strip().lower()
        if ai_provider not in {"doubao", "qwen"}:
            errors.append("AI_PROVIDER 在生产环境必须为 doubao 或 qwen，禁止 mock")
        if not self.AI_API_KEY:
            errors.append("AI_API_KEY 在生产环境必须配置")
        if not self.AI_API_BASE.lower().startswith("https://"):
            errors.append("AI_API_BASE 在生产环境必须使用 HTTPS")

        oss_provider = self.OSS_PROVIDER.strip().lower()
        if oss_provider not in {"aliyun", "tencent"}:
            errors.append("OSS_PROVIDER 在生产环境必须为 aliyun 或 tencent，禁止 local")
        elif oss_provider == "aliyun":
            for field_name, value in {
                "OSS_ACCESS_KEY": self.OSS_ACCESS_KEY,
                "OSS_SECRET_KEY": self.OSS_SECRET_KEY,
                "OSS_BUCKET": self.OSS_BUCKET,
                "OSS_ENDPOINT": self.OSS_ENDPOINT,
            }.items():
                if not value:
                    errors.append(f"{field_name} 在生产环境使用阿里云 OSS 时必须配置")
            if self.OSS_ENDPOINT and not self.OSS_ENDPOINT.lower().startswith("https://"):
                errors.append("OSS_ENDPOINT 在生产环境必须使用 HTTPS")
            if self.OSS_CDN_DOMAIN and not self.OSS_CDN_DOMAIN.lower().startswith("https://"):
                errors.append("OSS_CDN_DOMAIN 在生产环境必须使用 HTTPS")
        else:
            for field_name, value in {
                "COS_SECRET_ID": self.COS_SECRET_ID,
                "COS_SECRET_KEY": self.COS_SECRET_KEY,
                "COS_BUCKET": self.COS_BUCKET,
                "COS_REGION": self.COS_REGION,
            }.items():
                if not value:
                    errors.append(f"{field_name} 在生产环境使用腾讯云 COS 时必须配置")
            if self.COS_CDN_DOMAIN and not self.COS_CDN_DOMAIN.lower().startswith("https://"):
                errors.append("COS_CDN_DOMAIN 在生产环境必须使用 HTTPS")

        map_provider = self.MAP_PROVIDER.strip().lower()
        if map_provider not in {"amap", "tencent"}:
            errors.append("MAP_PROVIDER 在生产环境必须为 amap 或 tencent，禁止 local 直线距离")
        elif map_provider == "amap" and not self.AMAP_API_KEY:
            errors.append("AMAP_API_KEY 在生产环境使用高德地图时必须配置")
        elif map_provider == "tencent" and not self.TENCENT_MAP_KEY:
            errors.append("TENCENT_MAP_KEY 在生产环境使用腾讯地图时必须配置")

        if errors:
            raise RuntimeError(
                "生产环境安全配置校验失败，拒绝启动：\n  - "
                + "\n  - ".join(errors)
            )

    class Config:
        # 锚定 server/.env，避免从不同 cwd 启动时静默退回 development 默认值。
        env_file = str(SERVER_ROOT / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
settings.validate_security()  # 模块加载即校验，生产环境不达标直接拒启动
