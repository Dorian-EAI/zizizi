"""结构化日志工具（JSON formatter，缺库 fallback 标准 logging）
同时支持文件输出，logs/app.log（全量）+ logs/error.log（ERROR+）

安全说明：
- 自动对 PII 字段（phone/id_card/password/token/openid）做掩码处理
- 防止敏感信息进入日志文件被日志采集系统抓取
"""

import logging
import logging.handlers
import sys
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")


def _ensure_log_dir():
    """确保日志目录存在"""
    if not os.path.isdir(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)


# PII 脱敏：字段名匹配规则
# 完全脱敏（用 *** 替换）
_PII_FULL_KEYS = {
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "secret_key", "api_key", "private_key", "session_key",
    "wx_secret", "jsapi_ticket",
}
# 部分脱敏（保留前缀/后缀）
_PII_PARTIAL_KEYS = {
    "phone": "phone",          # 138****8000
    "id_card": "id_card",      # 3501**********1234
    "openid": "openid",        # 前4后4
    "unionid": "unionid",
    "bank_card": "bank_card",  # 前4后4
    "bank_info": "bank_info",
    "real_name": "real_name",  # 姓名仅保留首字
}


def _mask_phone(v: str) -> str:
    if not v or len(v) < 7:
        return "***"
    return v[:3] + "*" * (len(v) - 7) + v[-4:]


def _mask_id_card(v: str) -> str:
    if not v or len(v) < 8:
        return "***"
    return v[:4] + "*" * (len(v) - 8) + v[-4:]


def _mask_short(v: str) -> str:
    """短字符串脱敏：保留首尾各 4 字符"""
    if not v or len(v) <= 8:
        return "***"
    return v[:4] + "*" * (len(v) - 8) + v[-4:]


def _mask_name(v: str) -> str:
    """姓名脱敏：仅保留首字"""
    if not v:
        return "***"
    return v[0] + "*" * (len(v) - 1) if len(v) > 1 else "*"


def _mask_value(key: str, value: Any) -> Any:
    """对单个字段值脱敏"""
    if value is None:
        return None
    key_lower = key.lower()

    # 完全脱敏字段
    if key_lower in _PII_FULL_KEYS or any(k in key_lower for k in _PII_FULL_KEYS):
        return "***"

    # 部分脱敏字段
    if not isinstance(value, str):
        # 非字符串的 PII 字段先转字符串
        if isinstance(value, (int, float)):
            value = str(value)
        else:
            return value

    if "phone" in key_lower:
        return _mask_phone(value)
    if "id_card" in key_lower:
        return _mask_id_card(value)
    if "openid" in key_lower or "unionid" in key_lower or "bank_card" in key_lower:
        return _mask_short(value)
    if "bank_info" in key_lower:
        return _mask_short(value)
    if "real_name" in key_lower or key_lower == "name":
        return _mask_name(value)

    return value


def _sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """递归脱敏字典中的 PII 字段"""
    if not isinstance(data, dict):
        return data
    sanitized = {}
    for k, v in data.items():
        if isinstance(v, dict):
            sanitized[k] = _sanitize_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [_sanitize_dict(x) if isinstance(x, dict) else x for x in v]
        else:
            sanitized[k] = _mask_value(k, v)
    return sanitized


# 日志消息中的手机号/身份证号正则（用于扫描 message 字段）
_PHONE_RE = re.compile(r"1[3-9]\d{9}")
_ID_CARD_RE = re.compile(r"\d{17}[\dXx]")


def _mask_in_text(text: str) -> str:
    """对日志 message 文本中的手机号/身份证号做掩码"""
    if not isinstance(text, str):
        return text
    # 手机号：138****8000
    text = _PHONE_RE.sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], text)
    # 身份证号：3501**********1234
    text = _ID_CARD_RE.sub(lambda m: m.group()[:4] + "*" * 10 + m.group()[-4:], text)
    return text


class PIISanitizingFilter(logging.Filter):
    """PII 脱敏过滤器

    安装到 handler 上，在 format 之前对 record 的 msg/args/extra 做脱敏
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # 脱敏 message
        try:
            msg = record.getMessage()
            masked = _mask_in_text(msg)
            if masked != msg:
                record.msg = masked
                record.args = None
        except Exception:
            pass

        # 脱敏 extra 字段
        for attr in ("phone", "id_card", "openid", "token", "password",
                     "real_name", "bank_info", "bank_card"):
            if hasattr(record, attr):
                try:
                    setattr(record, attr, _mask_value(attr, getattr(record, attr)))
                except Exception:
                    pass

        # 脱敏 record.__dict__ 中的其他 PII 字段（如 custom extra）
        for k in list(record.__dict__.keys()):
            if k in ("msg", "args", "levelname", "name", "levelno", "pathname",
                     "filename", "module", "exc_info", "exc_text", "stack_info",
                     "lineno", "funcName", "created", "msecs", "relativeCreated",
                     "thread", "threadName", "processName", "process", "getMessage",
                     "taskName"):
                continue
            try:
                v = record.__dict__[k]
                if isinstance(v, dict):
                    record.__dict__[k] = _sanitize_dict(v)
                elif isinstance(v, str):
                    masked = _mask_value(k, v)
                    if masked != v:
                        record.__dict__[k] = masked
            except Exception:
                pass

        return True  # 允许所有日志通过


class JsonFormatter(logging.Formatter):
    """JSON 日志 formatter（含 PII 脱敏）"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 收集 extra 字段（非标准 LogRecord 属性）
        std_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "getMessage", "taskName"
        }
        extra = {}
        for k, v in record.__dict__.items():
            if k not in std_attrs:
                if isinstance(v, dict):
                    extra[k] = _sanitize_dict(v)
                else:
                    extra[k] = _mask_value(k, v)
        if extra:
            log_entry["extra"] = extra

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def _setup_stdlib_handlers(logger: logging.Logger):
    """为标准 logging.Logger 配置文件 + 控制台 handler"""
    _ensure_log_dir()

    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return

    try:
        formatter = JsonFormatter()
    except Exception:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    pii_filter = PIISanitizingFilter()

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(pii_filter)
    logger.addHandler(console_handler)

    # 全量文件日志（带轮转，单文件 10MB，保留 5 个）
    app_log_path = os.path.join(LOG_DIR, "app.log")
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            app_log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
    except Exception:
        file_handler = logging.FileHandler(app_log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(pii_filter)
    logger.addHandler(file_handler)

    # ERROR 及以上单独写入 error.log
    error_log_path = os.path.join(LOG_DIR, "error.log")
    try:
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
    except Exception:
        error_handler = logging.FileHandler(error_log_path, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(pii_filter)
    logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """获取结构化 logger（优先 structlog，否则 JSON formatter，最后标准 Logger）

    无论哪种实现，都会附加文件日志（app.log 全量 + error.log ERROR+）
    所有日志都会经过 PII 脱敏过滤器
    """
    _ensure_log_dir()

    if HAS_STRUCTLOG:
        try:
            structlog.configure_once(
                processors=[
                    structlog.stdlib.filter_by_level,
                    structlog.stdlib.add_logger_name,
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.TimeStamper(fmt="iso", utc=True),
                    structlog.processors.StackInfoRenderer(),
                    structlog.processors.format_exc_info,
                    structlog.processors.UnicodeDecoder(),
                    # 自定义 PII 脱敏 processor
                    lambda _logger, _method_name, event_dict: _sanitize_event_dict(event_dict),
                    structlog.processors.JSONRenderer(ensure_ascii=False),
                ],
                context_class=dict,
                logger_factory=structlog.stdlib.LoggerFactory(),
                wrapper_class=structlog.stdlib.BoundLogger,
                cache_logger_on_first_use=True,
            )

            base_logger = logging.getLogger(name)
            _setup_stdlib_handlers(base_logger)
            return structlog.get_logger(name)
        except Exception:
            pass

    logger = logging.getLogger(name)
    _setup_stdlib_handlers(logger)
    return logger


def _sanitize_event_dict(event_dict: dict) -> dict:
    """structlog 专用：脱敏 event_dict 中的 PII 字段"""
    if not isinstance(event_dict, dict):
        return event_dict

    # event 字段是消息主体，扫描其中的手机号/身份证号
    if "event" in event_dict and isinstance(event_dict["event"], str):
        event_dict["event"] = _mask_in_text(event_dict["event"])

    for k, v in list(event_dict.items()):
        if k == "event":
            continue
        if isinstance(v, dict):
            event_dict[k] = _sanitize_dict(v)
        else:
            event_dict[k] = _mask_value(k, v)
    return event_dict

