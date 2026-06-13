from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AbilityScores(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    str_: int = Field(ge=3, le=30, alias="str")
    dex: int = Field(ge=3, le=30)
    con: int = Field(ge=3, le=30)
    int_: int = Field(ge=3, le=30, alias="int")
    wis: int = Field(ge=3, le=30)
    cha: int = Field(ge=3, le=30)


class CreateCharacterRequest(BaseModel):
    module_id: str
    name: str
    race: str
    char_class: str
    subclass: Optional[str] = None
    level: int = 1
    background: Optional[str] = None
    alignment: Optional[str] = None
    ability_scores: AbilityScores
    proficient_skills: list[str] = []
    known_spells: list[str] = []
    cantrips: list[str] = []
    multiclass_info: Optional[dict] = None
    fighting_style: Optional[str] = None
    equipment_choice: Optional[int] = None
    bonus_languages: list[str] = []
    feats: list[dict] = []
    personality: Optional[str] = None
    backstory: Optional[str] = None
    speech_style: Optional[str] = None
    combat_preference: Optional[str] = None
    catchphrase: Optional[str] = None


class GeneratePartyRequest(BaseModel):
    module_id: str
    player_character_id: str
    party_size: int = 4


class PreparedSpellsRequest(BaseModel):
    prepared_spells: list[str]


class LevelUpRequest(BaseModel):
    use_average_hp: bool = True
    ability_score_increases: Optional[dict] = None
    feat_choice: Optional[dict] = None
    learned_spells: list[str] = []
    learned_cantrips: list[str] = []


class GoldRequest(BaseModel):
    amount: int
    reason: str = ""


class ExhaustionRequest(BaseModel):
    change: int = 1


class AmmoRequest(BaseModel):
    weapon_name: str
    change: int = -1


class EquipmentUpdateRequest(BaseModel):
    item_name: str
    item_category: str
    equip: bool = True


class EquipmentBulkUpdateRequest(BaseModel):
    equipment: dict


class BuyItemRequest(BaseModel):
    item_name: str
    item_category: str
    quantity: int = 1


class SellItemRequest(BaseModel):
    item_name: str
    item_category: str
    item_index: int = 0


class TransferItemRequest(BaseModel):
    target_character_id: str
    item_name: str
    item_category: str
    item_index: int = 0


class UseItemRequest(BaseModel):
    item_name: str
    session_id: Optional[str] = None
    use_in_combat: bool = False
    target_character_id: Optional[str] = None
