"""微信小程序接口调用"""

import hashlib
import httpx
from fastapi import HTTPException

from app.config import settings


async def code2session(code: str) -> dict:
    """调用微信 code2session 接口，返回 {openid, session_key, unionid}

    Mock 模式：当 WX_APPID 或 WX_SECRET 留空时启用（对齐 .env 注释"留空=mock 登录"）。
    用 code 派生稳定 openid，便于开发期同一 code 复现同一用户。
    """
    if not settings.WX_APPID or not settings.WX_SECRET:
        if settings.is_deployed:
            raise HTTPException(status_code=503, detail="微信登录服务未配置")
        # Mock 分支：code → 稳定 openid（同一 code 同一用户，便于联调）
        h = hashlib.sha1(code.encode("utf-8")).hexdigest()
        return {
            "openid": "mock_" + h[:24],
            "session_key": "mock_session_" + h[:16],
            "unionid": None,
        }

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.WX_APPID,
        "secret": settings.WX_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="微信登录服务暂不可用") from exc

    if data.get("errcode", 0) != 0:
        raise HTTPException(status_code=401, detail="微信登录凭证无效或已过期")
    return data
