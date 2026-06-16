from typing import Literal, Optional

from pydantic import BaseModel, Field


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
    idempotency_key: Optional[str] = Field(default=None, max_length=80)


class SkillCheckRequest(BaseModel):
    session_id: str
    character_id: str
    skill: str
    dc: int
    d20_value: Optional[int] = None
    second_d20_value: Optional[int] = None
    use_lucky: bool = False
    lucky_d20_value: Optional[int] = None
    use_bardic_inspiration: bool = False
    bardic_inspiration_roll: Optional[int] = None


class AITakeoverRequest(BaseModel):
    session_id: str


class ClaimLootRequest(BaseModel):
    character_id: str
    loot_id: str
    claim_mode: Literal["claim", "split_party", "party_stash", "roll_party"] = "claim"


class SelectEncounterTemplateRequest(BaseModel):
    template_id: str


class ExplorationReactionRequest(BaseModel):
    reaction_type: Literal["feather_fall", "decline"]
    character_id: Optional[str] = None
