from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.deps import get_authorized_session, get_session_or_404, get_user_id
from database import get_db
from models import GameLog, Module
from schemas.game_responses import RestResponse
from services.langgraph_client import langgraph_client
from services.rest_service import apply_party_rest

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/sessions/{session_id}/journal")
async def generate_journal(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Generate a short campaign journal from recent adventure logs."""
    session = await get_authorized_session(session_id, db, user_id)
    module = await db.get(Module, session.module_id)
    log_result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .order_by(GameLog.created_at.asc())
        .limit(80)
    )
    logs = log_result.scalars().all()
    if not logs:
        return {"journal": "还没有冒险记录可以生成日志。"}

    log_text = "\n".join(f"[{log.role}] {log.content}" for log in logs if log.content)
    module_summary = (module.parsed_content or {}).get("plot_summary", "") if module else ""
    try:
        from langchain_core.messages import HumanMessage as _HM, SystemMessage as _SM
        from services.llm import get_llm

        llm = get_llm(temperature=0.8, max_tokens=800, task="fast")
        resp = await llm.ainvoke([
            _SM(content="你是一位文笔出色的 DnD 5e 编年史作者，擅长将冒险记录改写为史诗般的战役日志。"),
            _HM(content=(
                f"## 模组背景\n{module_summary}\n\n"
                f"## 冒险记录\n{log_text[-3000:]}\n\n"
                "请以第三人称叙事风格，为这段冒险旅程写一篇简短的战役日志，约 400 字。"
                "包含英雄们的行动、遭遇的危险、关键事件和转折。"
                "语气史诗而有情感，像奇幻小说的章节摘要。"
                "直接输出日志正文，不要前缀、标签或 JSON。"
            )),
        ])
        journal_text = resp.content.strip()
        if not journal_text or len(journal_text) < 20:
            journal_text = "日志生成失败"
    except Exception as exc:
        journal_text = f"（AI日志生成失败：{exc}）\n\n以下为原始记录节选：\n\n{log_text[:800]}"

    state = dict(session.game_state or {})
    state["last_journal"] = journal_text
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return {"journal": journal_text, "log_count": len(logs)}


@router.post("/sessions/{session_id}/checkpoint")
async def save_checkpoint(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Compress recent adventure logs into structured campaign state."""
    session = await get_authorized_session(session_id, db, user_id)
    module = await db.get(Module, session.module_id)
    log_result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .where(GameLog.log_type.in_(["narrative", "companion", "combat"]))
        .order_by(GameLog.created_at.asc())
        .limit(120)
    )
    logs = log_result.scalars().all()
    if not logs:
        return {"ok": False, "message": "没有可以存档的内容"}

    log_text = "\n".join(f"[{log.role}] {log.content}" for log in logs if log.content)
    module_summary = (module.parsed_content or {}).get("plot_summary", "") if module else ""
    try:
        new_campaign_state = await langgraph_client.generate_campaign_state(
            log_text=log_text[-4000:],
            module_summary=module_summary,
            existing_state=session.campaign_state or {},
        )
    except Exception as exc:
        raise HTTPException(502, f"档案生成失败: {exc}") from exc

    session.campaign_state = new_campaign_state
    await db.commit()
    return {"ok": True, "campaign_state": new_campaign_state}


@router.get("/sessions/{session_id}/checkpoint")
async def get_checkpoint(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Return the current structured campaign checkpoint."""
    session = await get_authorized_session(session_id, db, user_id)
    return {
        "session_id": session_id,
        "campaign_state": session.campaign_state or {},
        "has_checkpoint": session.campaign_state is not None,
    }


@router.post("/sessions/{session_id}/rest", response_model=RestResponse)
async def take_rest(
    session_id: str,
    rest_type: str = "long",
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Apply a party rest. Multiplayer rooms must use rest voting instead."""
    if rest_type not in ("long", "short"):
        raise HTTPException(400, "rest_type 必须为 'long' 或 'short'")

    session = await get_authorized_session(session_id, db, user_id)
    if session.is_multiplayer:
        raise HTTPException(409, "多人模式下休息需要通过房间投票")

    result = await apply_party_rest(db, session, rest_type)
    await db.commit()
    return result
