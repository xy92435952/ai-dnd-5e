from models.session import GameLog, Session
from services.state_apply_result import ApplyResult


def append_session_history(session: Session, ar: ApplyResult) -> None:
    max_history = 4000
    history = session.session_history or ""

    new_lines = []
    if ar.narrative:
        new_lines.append(f"DM：{ar.narrative}")
    if ar.companion_reactions:
        new_lines.append(ar.companion_reactions)

    appended = "\n".join(new_lines)
    combined = f"{history}\n{appended}" if history else appended

    if len(combined) > max_history:
        cutoff = combined[-max_history:]
        boundary = cutoff.find("\nDM：")
        if boundary != -1:
            cutoff = cutoff[boundary:]
        combined = cutoff

    session.session_history = combined.strip()


async def write_game_logs(
    db,
    *,
    session: Session,
    ar: ApplyResult,
    full_data: dict,
) -> None:
    logs_to_add = []
    visibility = full_data.get("visibility") if isinstance(full_data.get("visibility"), dict) else None
    table_reason = full_data.get("table_reason") if isinstance(full_data.get("table_reason"), str) else None
    table_decision = full_data.get("table_decision") if isinstance(full_data.get("table_decision"), dict) else None

    if ar.narrative:
        logs_to_add.append(GameLog(
            session_id=session.id,
            role="dm",
            content=ar.narrative,
            log_type="narrative" if "combat" not in ar.action_type else "combat",
            dice_result=ar.dice_display or None,
            visibility=visibility,
            table_reason=table_reason,
            table_decision=table_decision,
        ))

    if ar.companion_reactions:
        logs_to_add.append(GameLog(
            session_id=session.id,
            role="companion",
            content=ar.companion_reactions,
            log_type="companion",
        ))

    for ai_turn in full_data.get("ai_turns", []):
        if ai_turn.get("narrative"):
            logs_to_add.append(GameLog(
                session_id=session.id,
                role=f"companion_{ai_turn.get('actor_name', 'ai')}",
                content=ai_turn["narrative"],
                log_type="combat",
                dice_result=ai_turn.get("dice_results"),
            ))

    for log in logs_to_add:
        db.add(log)
