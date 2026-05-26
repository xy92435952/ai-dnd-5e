from typing import Literal, Optional

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    module_id: str
    player_character_id: str
    companion_ids: list[str]
    save_name: Optional[str] = None
    dm_style: Optional[str] = None


class PlayerActionRequest(BaseModel):
    session_id: str
    action_text: str
    action_source: Literal["human_input", "ai_generated_choice", "system_action", "ai_takeover"] = "human_input"


class SkillCheckRequest(BaseModel):
    session_id: str
    character_id: str
    skill: str
    dc: int
    d20_value: Optional[int] = None
    second_d20_value: Optional[int] = None


class AITakeoverRequest(BaseModel):
    session_id: str
