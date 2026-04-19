from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from database import Base
import uuid


class SessionMember(Base):
    """多人联机房间成员

    - 单人 session 不会创建 SessionMember 记录
    - host 角色：role="host"，每个 session 仅一个；其他成员 role="player"
    - character_id 为 NULL 表示已加入但未选/创建角色
    - last_seen_at 由 WebSocket 心跳更新，用于断线检测（>30s 视为离线 → AI 托管）
    """
    __tablename__ = "session_members"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id   = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    user_id      = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(String, ForeignKey("characters.id"), nullable=True)
    role         = Column(String(20), default="player")  # host / player
    joined_at    = Column(DateTime, server_default=func.now())
    last_seen_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_session_user"),
    )
