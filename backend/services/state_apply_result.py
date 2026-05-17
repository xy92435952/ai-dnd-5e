from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ApplyResult:
    """StateApplicator.apply() 的返回值，供 API 层决策用。"""
    narrative: str = ""
    action_type: str = "unknown"
    companion_reactions: str = ""
    dice_display: list = field(default_factory=list)
    player_choices: list = field(default_factory=list)
    needs_check: dict = field(default_factory=lambda: {"required": False})
    combat_triggered: bool = False
    combat_ended: bool = False
    combat_end_result: Optional[str] = None
    initial_enemies: list = field(default_factory=list)
    errors: list = field(default_factory=list)
