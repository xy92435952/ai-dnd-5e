from models import Session


def choice_text(choice) -> str:
    if isinstance(choice, str):
        return choice.strip()
    if isinstance(choice, dict):
        return str(choice.get("text") or "").strip()
    return ""


def normalize_action_source(session: Session, action_text: str, requested_source: str) -> str:
    """Only server-stored previous choices can be trusted as AI-generated choices."""
    if requested_source != "ai_generated_choice":
        return requested_source

    last_turn = (session.game_state or {}).get("last_turn") or {}
    choices = last_turn.get("player_choices") or []
    normalized_text = (action_text or "").strip()
    if any(choice_text(choice) == normalized_text for choice in choices):
        return "ai_generated_choice"
    return "human_input"
