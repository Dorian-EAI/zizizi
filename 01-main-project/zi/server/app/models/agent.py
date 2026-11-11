"""AI 下单 Agent 会话模型

会话状态（槽位、草稿、确认令牌）统一存放在 state_json，便于对话轮次
之间恢复；status 列同时冗余一份，便于运营侧按状态排查异常会话。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class AgentSession(Base):
    """用户与 AI 下单助手的一次对话"""

    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_no = Column(String(48), unique=True, index=True, nullable=False, comment="会话编号")
    user_id = Column(Integer, index=True, nullable=False, comment="所属用户 ID")
    # collecting=补全信息 / awaiting_confirm=待确认 / creating=提交中 / created=已下单
    status = Column(String(24), nullable=False, default="collecting", comment="会话状态")
    state_json = Column(Text, nullable=False, default="{}", comment="槽位、草稿与确认令牌")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
        nullable=False,
    )
