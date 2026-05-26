"""多人联机房间相关的请求/响应 Pydantic Schema。"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ── 请求 ─────────────────────────────────────────────

class CreateRoomRequest(BaseModel):
    module_id: str
    save_name: Optional[str] = None
    max_players: int = Field(default=4, ge=2, le=4)
    dm_style: Optional[str] = None


class JoinRoomRequest(BaseModel):
    room_code: str = Field(min_length=6, max_length=6)


class ClaimCharacterRequest(BaseModel):
    character_id: str


class KickMemberRequest(BaseModel):
    user_id: str


class TransferHostRequest(BaseModel):
    new_host_user_id: str


class SetGroupRequest(BaseModel):
    group_id: str = Field(default="main", min_length=1, max_length=40)
    group_name: Optional[str] = Field(default=None, max_length=40)
    location: Optional[str] = Field(default=None, max_length=80)


class SubmitGroupActionRequest(BaseModel):
    group_id: str = Field(default="main", min_length=1, max_length=40)
    action_text: str = Field(min_length=1, max_length=500)


class ClearGroupActionsRequest(BaseModel):
    group_id: str = Field(default="main", min_length=1, max_length=40)


class FocusGroupRequest(BaseModel):
    group_id: str = Field(default="main", min_length=1, max_length=40)


class SetGroupReadinessRequest(BaseModel):
    group_id: str = Field(default="main", min_length=1, max_length=40)
    status: str = Field(min_length=1, max_length=20)


class SetStartReadyRequest(BaseModel):
    ready: bool = True


# ── 响应 ─────────────────────────────────────────────

class MemberInfo(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str  # host / player
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    is_online: bool = False
    seconds_since_seen: Optional[int] = None
    joined_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AiCompanionInfo(BaseModel):
    id: str
    name: str
    race: Optional[str] = None
    char_class: Optional[str] = None
    level: Optional[int] = None
    hp_max: Optional[int] = None
    base_hp_max: Optional[int] = None

    class Config:
        from_attributes = True


class RoomInfo(BaseModel):
    session_id: str
    room_code: Optional[str]
    module_id: str
    save_name: Optional[str]
    host_user_id: Optional[str]
    max_players: int
    is_multiplayer: bool
    game_started: bool  # 派生字段：current_scene 非空且 combat 已初始化
    members: List[MemberInfo] = []
    ai_companions: List[AiCompanionInfo] = []
    current_speaker_user_id: Optional[str] = None
    speak_round: int = 0
    party_groups: List[dict] = []
    active_group_id: Optional[str] = None
    pending_actions_by_group: dict = {}
    group_readiness: dict = {}
    room_votes: List[dict] = []
    start_ready_user_ids: List[str] = []
    dm_style: Optional[dict] = None
    created_at: Optional[datetime] = None


class CreateRoomResponse(BaseModel):
    session_id: str
    room_code: str
    host_user_id: str


class JoinRoomResponse(BaseModel):
    session_id: str
    room_code: str
    your_member_id: str
    members: List[MemberInfo]
