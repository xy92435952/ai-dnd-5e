"""
游戏会话路由聚合入口。

具体业务已拆到 api.game_routes.* 和 services.game_*：
- sessions: 存档创建/列表/详情/删除
- actions: /game/action 与 AI 代演
- checks: 技能检定
- campaign: 战役日志、checkpoint、休息

本模块保留旧 helper 名称的 re-export，兼容测试和历史 import。
"""
from fastapi import APIRouter

from api.game_routes import actions, campaign, checks, sessions
from schemas.game_requests import (
    AITakeoverRequest,
    CreateSessionRequest,
    PlayerActionRequest,
    SavingThrowRequest,
    SkillCheckRequest,
)
from services.game_action_source_service import (
    choice_text as _choice_text,
    normalize_action_source as _normalize_action_source,
)
from services.game_combat_setup_service import (
    build_enemy_from_module as _build_enemy_from_module,
    init_combat as _init_combat,
)
from services.game_exploration_service import execute_exploration_action as _execute_exploration_action
from services.game_multiplayer_service import (
    apply_multiplayer_room_decision as _apply_multiplayer_room_decision,
    broadcast_multiplayer_table_message as _broadcast_multiplayer_table_message,
    find_next_ready_group_id as _find_next_ready_group_id,
    send_dm_responded_with_visibility as _send_dm_responded_with_visibility,
)
from services.game_opening_service import generate_opening as _generate_opening

router = APIRouter()
router.include_router(sessions.router)
router.include_router(actions.router)
router.include_router(checks.router)
router.include_router(campaign.router)

create_session = sessions.create_session
list_sessions = sessions.list_sessions
get_session = sessions.get_session
delete_session = sessions.delete_session
player_action = actions.player_action
ai_takeover_action = actions.ai_takeover_action
skill_check = checks.skill_check
saving_throw = checks.saving_throw
generate_journal = campaign.generate_journal
save_checkpoint = campaign.save_checkpoint
get_checkpoint = campaign.get_checkpoint
take_rest = campaign.take_rest

__all__ = [
    "router",
    "CreateSessionRequest",
    "PlayerActionRequest",
    "SkillCheckRequest",
    "SavingThrowRequest",
    "AITakeoverRequest",
    "_choice_text",
    "_normalize_action_source",
    "_apply_multiplayer_room_decision",
    "_find_next_ready_group_id",
    "_broadcast_multiplayer_table_message",
    "_send_dm_responded_with_visibility",
    "_execute_exploration_action",
    "_generate_opening",
    "_build_enemy_from_module",
    "_init_combat",
    "create_session",
    "list_sessions",
    "get_session",
    "delete_session",
    "player_action",
    "ai_takeover_action",
    "skill_check",
    "saving_throw",
    "generate_journal",
    "save_checkpoint",
    "get_checkpoint",
    "take_rest",
]
