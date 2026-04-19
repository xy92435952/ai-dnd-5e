from sqlalchemy import Column, String, Integer, Text, Boolean, JSON, ForeignKey, DateTime
from sqlalchemy.sql import func
from database import Base
import uuid


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True, index=True)  # 所属用户
    module_id = Column(String, ForeignKey("modules.id"), nullable=False)
    player_character_id = Column(String, nullable=True)  # 延迟绑定

    # 游戏状态
    current_scene = Column(Text, nullable=True)
    session_history = Column(Text, default="")   # 压缩后的历史摘要
    game_state = Column(JSON, default=dict)       # 剧情进度flags、已触发事件等
    combat_active = Column(Boolean, default=False)

    # 结构化跨session记忆（checkpoint时由AI生成）
    campaign_state = Column(JSON, nullable=True)

    # Dify Chatflow 对话 ID（每个 session 对应一条 Chatflow 对话，实现跨轮次原生记忆）
    dify_conversation_id = Column(String, nullable=True)

    # 存档名
    save_name = Column(String(100), nullable=True)

    # ── 多人联机字段（v0.9 起）────────────────────────────
    is_multiplayer = Column(Boolean, default=False, nullable=False)
    room_code      = Column(String(6), nullable=True, unique=True, index=True)
    host_user_id   = Column(String, ForeignKey("users.id"), nullable=True)
    max_players    = Column(Integer, default=4, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CombatState(Base):
    __tablename__ = "combat_states"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)

    grid_data = Column(JSON, default=dict)         # 地形、障碍物 {x_y: "wall/difficult"}
    entity_positions = Column(JSON, default=dict)  # {character_id: {x, y}}
    turn_order = Column(JSON, default=list)        # [{character_id, initiative, name}]
    current_turn_index = Column(Integer, default=0)
    round_number = Column(Integer, default=1)
    combat_log = Column(JSON, default=list)        # 战斗叙述记录
    turn_states = Column(JSON, default=dict)       # {entity_id: turn_state_dict} 行动配额追踪

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class GameLog(Base):
    __tablename__ = "game_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)

    role = Column(String(50), nullable=False)     # dm/player/companion_{name}/system
    content = Column(Text, nullable=False)
    log_type = Column(String(20), default="narrative")  # narrative/combat/dice/companion/system
    dice_result = Column(JSON, nullable=True)     # 骰子结果

    created_at = Column(DateTime, server_default=func.now())
