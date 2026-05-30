from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.deps import assert_session_access, get_session_or_404, get_user_id
from database import get_db
from models import Module
from schemas.game_requests import SelectEncounterTemplateRequest
from services.encounter_template_service import select_encounter_template
from services.location_graph_service import ensure_location_graph_state, public_location_graph
from services.module_content import get_module_content

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/sessions/{session_id}/encounter-template/select")
async def select_session_encounter_template(
    session_id: str,
    req: SelectEncounterTemplateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    module = await db.get(Module, session.module_id) if session.module_id else None
    game_state = ensure_location_graph_state(
        session.game_state or {},
        get_module_content(module),
    )
    try:
        updated_state, selected = select_encounter_template(game_state, req.template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session.game_state = updated_state
    flag_modified(session, "game_state")
    await db.commit()
    await db.refresh(session)
    return {
        "template": selected,
        "location_graph": public_location_graph((session.game_state or {}).get("location_graph")),
    }
