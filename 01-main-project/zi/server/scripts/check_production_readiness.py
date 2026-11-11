#!/usr/bin/env python3
"""发布门禁：在上传体验版或正式版前执行安全、画布、脚本和可选在线检查。

该脚本只做读取与连通性检查，不创建表、不迁移数据库、不发送短信或资金请求。
返回码为 0 才表示本次所选检查全部通过。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


SERVER_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SERVER_ROOT.parent
WXAPP_ROOT = WORKSPACE_ROOT / "wxapp"
IGNORED_SOURCE_PARTS = {".backups", ".git", "node_modules", "miniprogram_npm"}


class Gate:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes: list[str] = []

    def require(self, condition: bool, success: str, failure: str) -> None:
        if condition:
            self.passes.append(success)
        else:
            self.failures.append(failure)

    def run(self, label: str, command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            self.failures.append(f"{label} 无法执行：{exc}")
            return
        if completed.returncode == 0:
            self.passes.append(label)
            return
        detail = (completed.stdout + "\n" + completed.stderr).strip()
        if len(detail) > 1600:
            detail = detail[-1600:]
        self.failures.append(f"{label} 失败（exit={completed.returncode}）\n{detail}")


def load_production_settings(gate: Gate, env_file: Path):
    sys.path.insert(0, str(SERVER_ROOT))
    old_cwd = Path.cwd()
    try:
        os.chdir(SERVER_ROOT)
        from app.config import Settings

        config = Settings(_env_file=str(env_file))
    except Exception as exc:
        gate.failures.append(f"无法加载配置：{exc}")
        return None
    finally:
        os.chdir(old_cwd)

    is_production = config.APP_ENV.strip().lower() == "production"
    gate.require(
        is_production,
        "APP_ENV=production",
        "APP_ENV 必须设置为 production",
    )
    validation_config = config if is_production else config.model_copy(update={"APP_ENV": "production"})
    try:
        validation_config.validate_security()
    except RuntimeError as exc:
        gate.failures.append(str(exc))
    else:
        if is_production:
            gate.passes.append("后端生产安全配置")
    return config


def check_wxapp_environment(gate: Gate, config) -> None:
    env_js = WXAPP_ROOT / "config" / "env.js"
    if not env_js.is_file():
        gate.failures.append(f"缺少小程序环境配置：{env_js}")
        return
    text = env_js.read_text(encoding="utf-8")
    project_config_path = WXAPP_ROOT / "project.config.json"
    try:
        project_config = json.loads(project_config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        gate.failures.append(f"无法读取小程序 project.config.json：{exc}")
        project_config = {}

    project_appid = str(project_config.get("appid") or "").strip()
    configured_appid = str(getattr(config, "WX_APPID", "") or "").strip()
    appid_valid = (
        bool(project_appid)
        and project_appid == configured_appid
        and not re.search(r"(?:tourist|example|your_|placeholder)", project_appid, re.I)
    )
    gate.require(
        appid_valid,
        "小程序 AppID 与后端 WX_APPID 一致",
        "project.config.json appid 必须与后端 WX_APPID 完全一致且不能是占位值",
    )
    gate.require(
        project_config.get("setting", {}).get("urlCheck") is True,
        "小程序已启用合法域名校验",
        "project.config.json setting.urlCheck 必须为 true",
    )
    private_config_path = WXAPP_ROOT / "project.private.config.json"
    if private_config_path.is_file():
        try:
            private_config = json.loads(private_config_path.read_text(encoding="utf-8"))
            private_url_check = private_config.get("setting", {}).get("urlCheck") is True
        except Exception as exc:
            private_url_check = False
            gate.failures.append(f"无法读取 project.private.config.json：{exc}")
        gate.require(
            private_url_check,
            "小程序私有配置未关闭合法域名校验",
            "project.private.config.json setting.urlCheck 必须为 true",
        )
    for name in ("trial", "release"):
        block_match = re.search(rf"\b{name}\s*:\s*\{{(?P<body>.*?)\n\s*\}}", text, re.S)
        if not block_match:
            gate.failures.append(f"小程序缺少 {name} 环境块")
            continue
        body = block_match.group("body")
        url_match = re.search(r"\bbaseURL\s*:\s*(['\"])(?P<url>.*?)\1", body)
        url = url_match.group("url").strip().rstrip("/") if url_match else ""
        parsed_url = urlsplit(url)
        url_valid = (
            parsed_url.scheme == "https"
            and bool(parsed_url.hostname)
            and parsed_url.username is None
            and parsed_url.password is None
            and not parsed_url.query
            and not parsed_url.fragment
            and ".example." not in url
        )
        gate.require(
            url_valid,
            f"小程序 {name} 使用真实 HTTPS API 域名",
            f"小程序 {name}.baseURL 必须填写真实 HTTPS API 域名",
        )
        if url_valid:
            gate.require(
                parsed_url.hostname in config.allowed_hosts_list,
                f"小程序 {name} API 域名属于后端 ALLOWED_HOSTS",
                f"小程序 {name}.baseURL 域名必须同时出现在后端 ALLOWED_HOSTS",
            )
        phone_match = re.search(r"\bservicePhone\s*:\s*(['\"])(?P<phone>.*?)\1", body)
        phone = re.sub(r"\D", "", phone_match.group("phone")) if phone_match else ""
        gate.require(
            5 <= len(phone) <= 20,
            f"小程序 {name} 已配置客服电话",
            f"小程序 {name}.servicePhone 必须填写真实客服电话",
        )
        gate.require(
            bool(re.search(r"\ballowMock\s*:\s*false\b", body))
            and bool(re.search(r"\buseMock\s*:\s*false\b", body)),
            f"小程序 {name} 禁用 Mock",
            f"小程序 {name} 必须设置 allowMock=false 且 useMock=false",
        )


def check_wxapp_sources(gate: Gate) -> None:
    json_failure_count = len(gate.failures)
    json_count = 0
    for path in WXAPP_ROOT.rglob("*.json"):
        relative_parts = path.relative_to(WXAPP_ROOT).parts
        if path.name.startswith("._") or any(part in IGNORED_SOURCE_PARTS for part in relative_parts):
            continue
        json_count += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            gate.failures.append(f"JSON 无效：{path.relative_to(WXAPP_ROOT)}：{exc}")
    if len(gate.failures) == json_failure_count:
        gate.passes.append(f"小程序 JSON 语法（{json_count} 个文件）")

    node = shutil.which("node")
    if not node:
        gate.failures.append("找不到 Node.js，无法校验小程序 JavaScript")
        return
    js_failure_count = len(gate.failures)
    js_count = 0
    for path in WXAPP_ROOT.rglob("*.js"):
        relative_parts = path.relative_to(WXAPP_ROOT).parts
        if path.name.startswith("._") or any(part in IGNORED_SOURCE_PARTS for part in relative_parts):
            continue
        js_count += 1
        completed = subprocess.run(
            [node, "--check", str(path)],
            cwd=WXAPP_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            detail = (completed.stdout + "\n" + completed.stderr).strip()
            gate.failures.append(f"JS 语法无效：{path.relative_to(WXAPP_ROOT)}\n{detail}")
    if len(gate.failures) == js_failure_count:
        gate.passes.append(f"小程序 JavaScript 语法（{js_count} 个文件）")


def subprocess_environment(config) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    for key, value in config.model_dump().items():
        if value is None:
            continue
        if isinstance(value, bool):
            env[key] = "true" if value else "false"
        else:
            env[key] = str(value)
    return env


def check_online_dependencies(gate: Gate, config) -> None:
    code = """
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from app.database import engine
from app.utils.redis_client import redis_client
from app.utils.rate_limit import _get_storage_uri
import redis
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
    table_names = set(inspect(conn).get_table_names())
    required_tables = {'alembic_version', 'page_contents', 'faq_categories', 'service_types', 'admins'}
    missing_tables = required_tables - table_names
    if missing_tables:
        raise SystemExit('数据库缺少必要表：' + ', '.join(sorted(missing_tables)))
    current_heads = set(MigrationContext.configure(conn).get_current_heads())
    expected_heads = set(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())
    if current_heads != expected_heads:
        raise SystemExit(f'Alembic 未到 head：current={sorted(current_heads)} expected={sorted(expected_heads)}')
    legal_keys = set(conn.execute(text(
        "SELECT `key` FROM page_contents WHERE `key` IN ('agreement','privacy','about','help') "
        "AND content IS NOT NULL AND LENGTH(TRIM(content)) > 0"
    )).scalars())
    missing_legal = {'agreement', 'privacy', 'about', 'help'} - legal_keys
    if missing_legal:
        raise SystemExit('运营内容未发布：' + ', '.join(sorted(missing_legal)))
    if not conn.execute(text('SELECT COUNT(*) FROM faq_categories')).scalar_one():
        raise SystemExit('FAQ 内容尚未发布')
    if not conn.execute(text('SELECT COUNT(*) FROM service_types WHERE is_active = 1')).scalar_one():
        raise SystemExit('没有启用的服务类目')
    if not conn.execute(text(
        "SELECT COUNT(*) FROM admins WHERE is_active = 1 AND role = 'super_admin' "
        "AND must_change_password = 0"
    )).scalar_one():
        raise SystemExit('没有已完成首次改密的启用超级管理员')
if not redis_client.ping():
    raise SystemExit('Redis ping 失败')
try:
    if not redis.Redis.from_url(
        _get_storage_uri(), socket_connect_timeout=2, socket_timeout=2
    ).ping():
        raise SystemExit('限流 Redis ping 失败')
except Exception as exc:
    raise SystemExit(f'限流 Redis ping 失败：{exc}')
print('数据库、迁移 head、运营内容、服务目录、管理员与 Redis 均可用')
""".strip()
    gate.run(
        "生产数据库、迁移版本与 Redis 连通性",
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        env=subprocess_environment(config),
    )


def check_provider_dependencies(gate: Gate, config) -> None:
    code = """
from app.utils.deployment_probe import assert_deployment_dependencies
assert_deployment_dependencies()
print('所选短信、对象存储、微信支付、限流与加密 SDK/密钥格式可用')
""".strip()
    gate.run(
        "生产 Provider SDK 与本地密钥格式",
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        env=subprocess_environment(config),
    )


def run_backend_tests(gate: Gate) -> None:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUTF8": "1",
            "APP_ENV": "testing",
            "APP_DEBUG": "false",
            "DB_DRIVER": "sqlite",
            "SQLITE_PATH": ":memory:",
        }
    )
    gate.run(
        "后端 unittest 回归",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=SERVER_ROOT,
        env=env,
    )
    openapi_code = """
from app.main import app
schema = app.openapi()
operation_ids = [op.get('operationId') for item in schema['paths'].values() for op in item.values() if isinstance(op, dict) and op.get('operationId')]
if len(operation_ids) != len(set(operation_ids)):
    raise SystemExit('OpenAPI operationId 重复')
print(f\"OpenAPI: {len(schema['paths'])} paths / {len(operation_ids)} operations\")
""".strip()
    gate.run(
        "OpenAPI 生成与 operationId 唯一性",
        [sys.executable, "-c", openapi_code],
        cwd=SERVER_ROOT,
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="自家人居家维修生产发布门禁")
    parser.add_argument("--env-file", type=Path, default=SERVER_ROOT / ".env")
    parser.add_argument("--online", action="store_true", help="连接生产数据库与 Redis 做只读探测")
    parser.add_argument("--run-tests", action="store_true", help="运行后端 unittest 与 OpenAPI 检查")
    parser.add_argument("--skip-design", action="store_true", help="仅紧急诊断使用；正式发布不得跳过画布检查")
    args = parser.parse_args()

    gate = Gate()
    env_file = args.env_file.resolve()
    gate.require(env_file.is_file(), "生产环境文件存在", f"环境文件不存在：{env_file}")
    config = load_production_settings(gate, env_file) if env_file.is_file() else None
    if config is not None and config.APP_ENV.strip().lower() == "production":
        check_provider_dependencies(gate, config)
    if config is not None:
        check_wxapp_environment(gate, config)
    else:
        gate.failures.append("后端配置无效，无法交叉校验小程序环境")
    check_wxapp_sources(gate)

    node = shutil.which("node")
    if not args.skip_design:
        if node:
            gate.run(
                "小程序运行完整性与 zjrnew.design 同步门禁",
                [node, "tools/release-gate.mjs"],
                cwd=WXAPP_ROOT,
            )
        else:
            gate.failures.append("找不到 Node.js，无法执行小程序运行完整性与 zjrnew.design 同步门禁")
    if args.run_tests:
        run_backend_tests(gate)
    if args.online:
        if config is None or config.APP_ENV.strip().lower() != "production":
            gate.failures.append("生产配置无效，跳过在线连通性检查")
        else:
            check_online_dependencies(gate, config)

    print(f"通过 {len(gate.passes)} 项；失败 {len(gate.failures)} 项")
    for item in gate.failures:
        print(f"\n[FAIL] {item}")
    if gate.failures:
        print("\n发布门禁未通过。修复以上项目后重新执行。")
        return 1
    print("\n发布门禁通过。仍需完成微信支付/退款回调、订阅消息及备份恢复的沙箱演练。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
