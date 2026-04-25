"""
游戏会话路由 — Session 管理 / 主跑团循环 / 技能检定 / 战役日志

架构说明（新版）：
  /game/action  ── 统一行动入口，战斗和探索都走这里
                   内部调用 ContextBuilder → DifyClient.call_dm_agent → StateApplicator
  其余端点（sessions CRUD / skill-check / journal / checkpoint / rest）保持不变
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import Module, Character, Session, GameLog, CombatState
from api.deps import get_session_or_404, char_brief, serialize_log, get_user_id
from services.langgraph_client import langgraph_client as dify_client
from services.dnd_rules import roll_skill_check, roll_initiative, roll_dice, _normalize_class, get_class_resource_defaults, HIT_DICE
from services.context_builder import ContextBuilder
from services.state_applicator import StateApplicator
from services.character_roster import CharacterRoster
from schemas.game_responses import (
    SessionListItem, SessionDetail, PlayerActionResponse,
    SkillCheckResult, RestResponse, CreateSessionResponse,
)

router = APIRouter(prefix="/game", tags=["game"])

import logging as _logging
_game_logger = _logging.getLogger(__name__)


# ── 开场白生成 ────────────────────────────────────────────

_OPENING_PROMPT = """你是一位经验丰富的 DnD 5e 地下城主，现在要为一场新冒险生成开场白。

## 你拥有的信息
- 模组名称：{module_name}
- 世界观/背景设定：{setting}
- 基调：{tone}
- 第一个场景的描述：{first_scene_desc}

## 开场白要求
1. **绝对不能剧透**——不要透露主线剧情走向、Boss身份、关键NPC的秘密、任何悬念的答案
2. **营造悬念**——用感官细节（异常的气味、远处的声响、不自然的沉寂）暗示"有什么不对劲"
3. **建立氛围**——让玩家感受到冒险的世界观基调（阴森/奇幻/史诗/诡异）
4. **引导行动**——结尾自然地让玩家产生"我想往前探索"的冲动，但不要直接列出选项
5. **第二人称叙述**——"你踏入..."、"你注意到..."
6. **200-300字**，中文，沉浸式文学风格
7. 不要使用 Markdown 格式，纯文本即可

直接输出开场白文本，不要有任何前缀、解释或标签。"""


async def _generate_opening(parsed: dict, raw_scene: str) -> str:
    """用 LLM 生成不剧透、有悬念的开场白。失败时回退到原始场景描述。"""
    try:
        from services.llm import get_llm
        llm = get_llm(temperature=0.85, max_tokens=600)

        prompt = _OPENING_PROMPT.format(
            module_name     = parsed.get("name", "未知模组"),
            setting         = parsed.get("setting", "一个神秘的奇幻世界"),
            tone            = parsed.get("tone", "冒险"),
            first_scene_desc = raw_scene or "冒险的起点",
        )

        from langchain_core.messages import SystemMessage, HumanMessage
        resp = await llm.ainvoke([
            SystemMessage(content="你是一位经验丰富的 DnD 5e 地下城主，擅长用沉浸式的文学语言描述场景。"),
            HumanMessage(content=prompt),
        ])
        text = resp.content.strip()
        if len(text) > 30:
            return text
    except Exception as e:
        _game_logger.warning(f"开场白生成失败，使用原始场景描述: {e}")

    # Fallback
    return raw_scene or f"你站在{parsed.get('setting', '一个神秘的地方')}的入口处。冒险即将开始。"


# ── Schemas ───────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    module_id:           str
    player_character_id: str
    companion_ids:       list[str]
    save_name:           Optional[str] = None


class PlayerActionRequest(BaseModel):
    session_id:  str
    action_text: str


class SkillCheckRequest(BaseModel):
    session_id:   str
    character_id: str
    skill:        str
    dc:           int
    d20_value:    Optional[int] = None  # Frontend 3D dice result


# ── Session 管理 ──────────────────────────────────────────

@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_user_id)):
    """创建游戏会话（开始新冒险）"""
    mod_result = await db.execute(select(Module).where(Module.id == req.module_id))
    module = mod_result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")

    parsed     = module.parsed_content or {}
    scenes     = parsed.get("scenes", [])
    raw_scene  = scenes[0]["description"] if scenes else ""

    # 用 AI 生成不剧透的开场白
    first_scene = await _generate_opening(parsed, raw_scene)

    session = Session(
        user_id              = user_id,
        module_id            = req.module_id,
        player_character_id  = req.player_character_id,
        current_scene        = first_scene,
        session_history      = "",
        game_state           = {"companion_ids": req.companion_ids, "scene_index": 0, "flags": {}},
        save_name            = req.save_name or f"冒险-{module.name}",
    )
    db.add(session)
    await db.flush()

    # 绑定角色到 session
    roster = CharacterRoster(db, session)
    await roster.bind_companions(req.companion_ids)

    player = await db.get(Character, req.player_character_id)
    if player:
        player.session_id = session.id

    db.add(GameLog(
        session_id = session.id,
        role       = "dm",
        content    = f"[开场] {first_scene}",
        log_type   = "narrative",
    ))
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, "opening_scene": first_scene}


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_user_id)):
    """获取当前用户的存档"""
    result   = await db.execute(select(Session).where(Session.user_id == user_id).order_by(Session.updated_at.desc()))
    sessions = result.scalars().all()
    out = []
    for s in sessions:
        mod    = await db.get(Module, s.module_id)
        player = await db.get(Character, s.player_character_id) if s.player_character_id else None
        out.append({
            "id":            s.id,
            "save_name":     s.save_name,
            "module_name":   mod.name if mod else "未知模组",
            "combat_active": s.combat_active,
            "updated_at":    s.updated_at.isoformat() if s.updated_at else None,
            "player_name":   player.name       if player else None,
            "player_class":  player.char_class if player else None,
            "player_level":  player.level      if player else None,
            "player_race":   player.race       if player else None,
        })
    return out


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取会话完整状态（用于恢复游戏）"""
    session    = await get_session_or_404(session_id, db)
    roster     = CharacterRoster(db, session)
    player     = await roster.player()
    module     = await db.get(Module, session.module_id) if session.module_id else None
    companions = [char_brief(c) for c in await roster.companions()]

    log_result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .order_by(GameLog.created_at.desc())
        .limit(50)
    )
    logs = list(reversed(log_result.scalars().all()))

    return {
        "session_id":     session.id,
        "save_name":      session.save_name,
        "module_id":      session.module_id,
        "module_name":    module.name if module else None,
        "current_scene":  session.current_scene,
        "combat_active":  session.combat_active,
        "game_state":     session.game_state or {},
        "player":         char_brief(player) if player else None,
        "companions":     companions,
        "logs":           [serialize_log(l) for l in logs],
        "campaign_state": session.campaign_state or {},
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_user_id)):
    """删除游戏存档及关联数据"""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "存档不存在")

    # 校验所有权
    if session.user_id and session.user_id != user_id:
        raise HTTPException(403, "无权删除他人的存档")

    # 清除所有角色对该 session 的引用（解除外键约束）
    from sqlalchemy import update as sql_update
    await db.execute(
        sql_update(Character).where(Character.session_id == session_id).values(session_id=None)
    )

    # 删除关联的战斗状态
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(CombatState).where(CombatState.session_id == session_id))

    # 删除关联的游戏日志
    await db.execute(sql_delete(GameLog).where(GameLog.session_id == session_id))

    # 删除关联的 AI 队友角色（非玩家角色）
    roster = CharacterRoster(db, session)
    await roster.delete_ai_companions()

    # 删除会话本身
    await db.delete(session)
    await db.commit()

    return {"ok": True}


# ── 主跑团循环（统一入口：战斗 + 探索） ─────────────────

@router.post("/action", response_model=PlayerActionResponse)
async def player_action(
    req: PlayerActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    玩家行动统一入口。
    战斗模式和探索模式都走这里，由 WF3 全能DM代理内部分流处理。
    返回 state_delta 由 StateApplicator 写库，前端通过 action_type 判断渲染方式。

    多人联机模式：
      - 探索阶段：仅当前发言者（multiplayer.current_speaker_user_id）能调用
      - 战斗阶段：仅当前回合归属玩家能调用
      - player 角色根据 user_id 在 SessionMember 中查找（不再用 session.player_character_id）
    """
    session = await get_session_or_404(req.session_id, db)
    module  = await db.get(Module, session.module_id)

    # ── 多人联机：解析当前用户对应的角色 ──
    if session.is_multiplayer:
        from models import SessionMember
        member_q = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session.id,
                SessionMember.user_id == user_id,
            )
        )
        member = member_q.scalar_one_or_none()
        if not member or not member.character_id:
            raise HTTPException(403, "你在该房间没有绑定角色")
        # 探索阶段：必须是当前发言者
        if not session.combat_active:
            mp = (session.game_state or {}).get("multiplayer", {})
            speaker = mp.get("current_speaker_user_id")
            if speaker and speaker != user_id:
                raise HTTPException(403, "现在不是你的发言时机，请等待 / 发言")
        player = await db.get(Character, member.character_id)

        # 广播"DM 思考中"给房间所有成员（在 LLM 调用前，让 B/C/D 同步看到等待状态）
        try:
            from services.ws_manager import ws_manager
            from schemas.ws_events import DMThinkingStart
            await ws_manager.broadcast(session.id, DMThinkingStart(
                by_user_id=user_id,
                action_text=req.action_text[:80],
            ))
        except Exception:
            pass
    else:
        player = await db.get(Character, session.player_character_id)

    # player 在多人模式下来自 SessionMember，单人模式下来自 session.player_character_id
    # companions 统一走 roster
    roster = CharacterRoster(db, session)
    characters: list[Character] = ([player] if player else []) + await roster.companions()

    # ── 加载战斗状态（如果在战斗中）──
    combat_state: Optional[CombatState] = None
    if session.combat_active:
        cs_res = await db.execute(
            select(CombatState)
            .where(CombatState.session_id == session.id)
            .order_by(CombatState.created_at.desc())
        )
        combat_state = cs_res.scalars().first()

    # ── 记录玩家行动 ──
    db.add(GameLog(
        session_id = req.session_id,
        role       = "player",
        content    = req.action_text,
        log_type   = "narrative" if not session.combat_active else "combat",
    ))

    # ═══════════════════════════════════════════════════════
    # 自然语言战斗：解析 → 引擎执行 → DM 叙事
    # ═══════════════════════════════════════════════════════
    if session.combat_active and combat_state and player:
        from services.action_parser import parse_combat_action
        from api.combat import _get_ts, _save_ts, _check_attack_range, _ai_move_toward, _chebyshev_dist, _calc_entity_turn_limits
        from services.combat_service import CombatService
        from services.combat_narrator import narrate_action

        svc = CombatService()
        positions = dict(combat_state.entity_positions or {})
        state = session.game_state or {}
        enemies = list(state.get("enemies", []))
        p_derived = player.derived or {}
        player_id = str(player.id)

        # 获取玩家回合状态
        ts = _get_ts(combat_state, player_id)
        move_remaining = ts["movement_max"] - ts["movement_used"]

        # 构建 game_state 给解析器
        gs_for_parser = {
            "characters": [{"id": c.id, "name": c.name, "hp_current": c.hp_current,
                            "hp_max": (c.derived or {}).get("hp_max", c.hp_current),
                            "is_player": c.is_player} for c in characters if c.hp_current > 0],
            "enemies": [{"id": e["id"], "name": e.get("name","?"),
                         "hp_current": e.get("hp_current",0), "hp_max": e.get("hp_max",0)}
                        for e in enemies if e.get("hp_current", 0) > 0],
        }

        # Step 1: AI 解析自然语言 → 结构化行动列表
        parsed = await parse_combat_action(
            player_input=req.action_text,
            game_state=gs_for_parser,
            player_id=player_id,
            player_data={"name": player.name, "hp_current": player.hp_current,
                         "hp_max": p_derived.get("hp_max", player.hp_current),
                         "ac": p_derived.get("ac", 10)},
            positions=positions,
            move_remaining=move_remaining,
        )

        # Step 2: 逐个执行行动
        action_results = []
        dice_display = []
        total_damage = 0
        target_new_hp = None
        action_used = False

        for action in parsed["actions"]:
            atype = action.get("type", "")

            if atype == "move" and not action_used:
                # 移动到目标旁边或指定位置
                move_target_id = action.get("target_id")
                move_target_pos = action.get("target_pos")

                if move_target_id:
                    dest = positions.get(str(move_target_id))
                elif move_target_pos:
                    dest = move_target_pos
                else:
                    continue

                if dest:
                    cur_pos = positions.get(player_id)
                    if cur_pos:
                        result = _ai_move_toward(cur_pos, dest, move_remaining, positions, player_id)
                        if result:
                            new_pos = {"x": result["x"], "y": result["y"]}
                            positions[player_id] = new_pos
                            combat_state.entity_positions = positions
                            ts["movement_used"] += result["steps"]
                            move_remaining -= result["steps"]
                            _save_ts(combat_state, player_id, ts)
                            action_results.append(f"移动了 {result['steps']*5}ft")

            elif atype == "attack" and not action_used:
                # 攻击
                target_id = action.get("target_id")
                is_ranged = action.get("is_ranged", False)

                # 如果没指定目标，找最近的敌人
                if not target_id:
                    player_pos = positions.get(player_id, {})
                    closest_dist = 999
                    for e in enemies:
                        if e.get("hp_current", 0) > 0:
                            epos = positions.get(str(e["id"]), {})
                            d = _chebyshev_dist(player_pos, epos)
                            if d < closest_dist:
                                closest_dist = d
                                target_id = e["id"]

                if target_id:
                    # 距离检查
                    atk_pos = positions.get(player_id)
                    tgt_pos = positions.get(str(target_id))
                    in_range, dist, _ = _check_attack_range(atk_pos, tgt_pos, is_ranged)

                    if not in_range:
                        action_results.append(f"目标不在攻击范围内（距离{dist*5}ft）")
                    else:
                        # 执行攻击
                        target_enemy = next((e for e in enemies if str(e["id"]) == str(target_id)), None)
                        if target_enemy:
                            target_derived = target_enemy.get("derived", {})
                            if not target_derived.get("ac"):
                                target_derived["ac"] = target_enemy.get("ac", 13)

                            attack_result = svc.resolve_melee_attack(
                                attacker_derived=p_derived,
                                target_derived=target_derived,
                                is_ranged=is_ranged,
                            )

                            d20 = attack_result.attack_roll.get("d20", 0)
                            hit = attack_result.attack_roll.get("hit", False)
                            is_crit = attack_result.attack_roll.get("is_crit", False)
                            damage = attack_result.damage

                            dice_display.append({
                                "label": "攻击检定", "dice_face": 20, "raw": d20,
                                "total": attack_result.attack_roll.get("attack_total", d20),
                                "against": f"AC {target_derived.get('ac', 13)}",
                                "outcome": "暴击" if is_crit else ("命中" if hit else "未命中"),
                            })

                            if hit:
                                target_enemy["hp_current"] = svc.apply_damage(
                                    target_enemy.get("hp_current", 0), damage,
                                    target_enemy.get("derived", {}).get("hp_max", 10),
                                )
                                target_new_hp = target_enemy["hp_current"]
                                total_damage += damage
                                dice_display.append({
                                    "label": "伤害", "dice_face": p_derived.get("hit_die", 8),
                                    "raw": damage, "total": damage,
                                })
                                crit_str = "暴击！" if is_crit else ""
                                action_results.append(f"{crit_str}攻击命中 {target_enemy.get('name','敌人')}，造成 {damage} 点伤害")
                                if target_new_hp <= 0:
                                    target_enemy["dead"] = True
                                    action_results.append(f"{target_enemy.get('name','敌人')} 被击倒！")
                            else:
                                action_results.append(f"攻击 {target_enemy.get('name','敌人')} 未命中（d20={d20}）")

                            state["enemies"] = enemies
                            session.game_state = dict(state)
                            flag_modified(session, "game_state")
                    action_used = True

            elif atype == "creative" and not action_used:
                # 创意行动 — 需要检定
                check_type = action.get("check_type", "str")
                dc = action.get("dc", 15)
                description = action.get("description", "创意行动")

                # 掷检定
                check_result = roll_skill_check(
                    character={"derived": p_derived, "proficient_skills": player.proficient_skills or []},
                    skill=check_type,
                    dc=dc,
                )
                d20 = check_result.get("d20", 10)
                total = check_result.get("total", 10)
                success = check_result.get("success", False)

                dice_display.append({
                    "label": f"{description} 检定", "dice_face": 20, "raw": d20,
                    "modifier": f"+{check_result.get('modifier',0)}",
                    "total": total, "against": f"DC {dc}",
                    "outcome": "成功" if success else "失败",
                })

                if success:
                    # 成功时应用伤害（如果有）
                    dmg_dice = action.get("damage_dice")
                    if dmg_dice:
                        dmg_roll = roll_dice(dmg_dice)
                        creative_dmg = dmg_roll["total"]
                        total_damage += creative_dmg
                        target_id = action.get("target_id")
                        if target_id:
                            target_enemy = next((e for e in enemies if str(e["id"]) == str(target_id)), None)
                            if target_enemy:
                                target_enemy["hp_current"] = svc.apply_damage(
                                    target_enemy.get("hp_current", 0), creative_dmg,
                                    target_enemy.get("derived", {}).get("hp_max", 10),
                                )
                                target_new_hp = target_enemy["hp_current"]
                                state["enemies"] = enemies
                                session.game_state = dict(state)
                                flag_modified(session, "game_state")
                        dice_display.append({"label": "伤害", "raw": creative_dmg, "total": creative_dmg})
                    action_results.append(f"{description} — 成功！（d20={d20}+{check_result.get('modifier',0)}={total} vs DC{dc}）" +
                                          (f" {action.get('effect_on_success','')}" if action.get('effect_on_success') else ""))
                else:
                    action_results.append(f"{description} — 失败（d20={d20}+{check_result.get('modifier',0)}={total} vs DC{dc}）" +
                                          (f" {action.get('effect_on_fail','')}" if action.get('effect_on_fail') else ""))
                action_used = True

            elif atype == "dodge" and not action_used:
                ts["dodging"] = True
                _save_ts(combat_state, player_id, ts)
                action_results.append("采取闪避动作，攻击你的敌人获得劣势")
                action_used = True

            elif atype == "dash" and not action_used:
                ts["movement_max"] *= 2
                _save_ts(combat_state, player_id, ts)
                action_results.append("冲刺！移动力翻倍")
                action_used = True

            elif atype == "disengage" and not action_used:
                ts["disengaged"] = True
                _save_ts(combat_state, player_id, ts)
                action_results.append("脱离接战，移动不触发借机攻击")
                action_used = True

        # 标记行动已使用
        if action_used:
            ts["action_used"] = True
            _save_ts(combat_state, player_id, ts)

        # Step 3: DM 叙事包装
        mechanical_summary = " | ".join(action_results) if action_results else "未执行有效行动"
        narrative = await narrate_action(
            actor_name=player.name,
            actor_class=player.char_class,
            target_name="",
            action_type="creative" if any(a.get("type") == "creative" for a in parsed["actions"]) else "attack",
            extra_details=f"玩家行动: {req.action_text}\n结果: {mechanical_summary}",
            damage=total_damage,
        )
        if not narrative:
            narrative = mechanical_summary

        # 检查战斗结束
        combat_over = False
        outcome = None
        alive_enemies = [e for e in enemies if e.get("hp_current", 0) > 0]
        if not alive_enemies:
            combat_over = True
            outcome = "victory"
            session.combat_active = False

        # 写日志
        db.add(GameLog(
            session_id=req.session_id, role="dm", content=narrative,
            log_type="combat", dice_result=dice_display if dice_display else None,
        ))

        # 构建 combat_update
        combat_update = {
            "entity_positions": dict(combat_state.entity_positions or {}),
            "turn_states": dict(combat_state.turn_states or {}),
            "current_turn_index": combat_state.current_turn_index,
            "round_number": combat_state.round_number,
        }

        await db.commit()

        return {
            "type":               "combat_action",
            "narrative":          narrative,
            "companion_reactions": "",
            "dice_display":       dice_display,
            "player_choices":     [],
            "needs_check":        {"required": False},
            "combat_triggered":   False,
            "combat_ended":       combat_over,
            "combat_end_result":  outcome,
            "combat_update":      combat_update,
            "action_results":     action_results,
            "errors":             [],
        }

    # ═══════════════════════════════════════════════════════
    # 探索模式：原有 DM Agent 流程
    # ═══════════════════════════════════════════════════════

    builder = ContextBuilder(
        session      = session,
        module       = module,
        characters   = characters,
        combat_state = combat_state,
    )
    # player 是当前行动者（单人=主角，多人=SessionMember 查到的角色）
    # 把 id 传下去让 DM 聚焦视角，避免分头行动时硬塞不在场的队友
    inputs = await builder.build(
        player_action=req.action_text,
        current_actor_id=player.id if player else None,
    )

    try:
        dm_result = await dify_client.call_dm_agent(
            **inputs,
            conversation_id=session.id,
        )
    except Exception as e:
        raise HTTPException(502, f"AI服务暂时不可用: {str(e)}")

    if not dm_result.get("success", True):
        raise HTTPException(502, f"DM代理处理失败: {dm_result.get('error', '未知错误')}")

    applicator = StateApplicator(db)
    ar = await applicator.apply(
        session      = session,
        result_json  = dm_result["result"],
        characters   = characters,
        combat_state = combat_state,
    )

    if ar.combat_triggered:
        await _init_combat(
            session         = session,
            initial_enemies = ar.initial_enemies,
            characters      = characters,
            module          = module,
            db              = db,
        )

    combat_update = None

    # 持久化最近一次回合的对话状态（供页面刷新 / WS 断线重连恢复）
    # - player_choices / needs_check 原本只在 HTTP 响应里返回，页面刷新后丢失
    # - last_actor_user_id 供前端判断"是不是我上次的选项"决定是否恢复
    gs = dict(session.game_state or {})  # 拷贝一份，避免引用问题
    gs["last_turn"] = {
        "player_choices":      ar.player_choices or [],
        "needs_check":         ar.needs_check if (ar.needs_check and ar.needs_check.get("required")) else None,
        "last_actor_user_id":  user_id,
        "action_type":         ar.action_type,
        "ts":                  datetime.utcnow().isoformat(),
    }
    session.game_state = gs
    flag_modified(session, "game_state")

    await db.commit()

    # 多人联机：广播 DM 响应到房间所有人
    # 携带**完整叙事 payload**，让其他玩家前端也能启动剧场模式
    # player_choices / needs_check 只给发言者（他们通过 HTTP 响应拿到），
    # WS 广播不带这些，避免误导非发言者
    # scene_vibe / clues 已写进 session.game_state，前端 loadSession 能拿到
    if session.is_multiplayer:
        from services.ws_manager import ws_manager
        from schemas.ws_events import DMResponded, DMSpeakTurn
        try:
            await ws_manager.broadcast(session.id, DMResponded(
                by_user_id=user_id,
                action_type=ar.action_type,
                narrative=ar.narrative,
                companion_reactions=ar.companion_reactions or "",
                dice_display=ar.dice_display or [],
                combat_triggered=ar.combat_triggered,
                combat_ended=ar.combat_ended,
            ))
        except Exception:
            pass

        # 真实跑团节奏：DM 回应后**自动**轮到下一位玩家
        # （之前玩家需要手动点"我说完了"，现在自动推进）
        # 探索阶段生效；战斗阶段由先攻顺序管理，不走这里
        if not session.combat_active and not ar.combat_triggered:
            try:
                from api.ws import _advance_speaker
                next_user = await _advance_speaker(db, session.id, user_id)
                if next_user:
                    await ws_manager.broadcast(session.id, DMSpeakTurn(
                        user_id=next_user, auto=True,
                    ))
            except Exception:
                pass

    return {
        "type":               ar.action_type,
        "narrative":          ar.narrative,
        "companion_reactions":ar.companion_reactions,
        "dice_display":       ar.dice_display,
        "player_choices":     ar.player_choices,
        "needs_check":        ar.needs_check,
        "combat_triggered":   ar.combat_triggered,
        "combat_ended":       ar.combat_ended,
        "combat_end_result":  ar.combat_end_result,
        "combat_update":      combat_update,
        "errors":             ar.errors,
    }


# ── 技能检定 ──────────────────────────────────────────────

@router.post("/skill-check", response_model=SkillCheckResult)
async def skill_check(req: SkillCheckRequest, db: AsyncSession = Depends(get_db)):
    """执行技能检定（正确检查角色是否熟练）"""
    char = await db.get(Character, req.character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    result = roll_skill_check(
        character        = {
            "derived":          char.derived,
            "proficient_skills":char.proficient_skills or [],
        },
        skill = req.skill,
        dc    = req.dc,
    )

    # Frontend dice override: use 3D physics result
    if req.d20_value is not None:
        d20_ov = req.d20_value
        modifier_ov = result["modifier"]
        total_ov = d20_ov + modifier_ov
        result = {
            **result,
            "d20": d20_ov,
            "total": total_ov,
            "success": total_ov >= req.dc,
        }

    db.add(GameLog(
        session_id  = req.session_id,
        role        = "system",
        content     = (
            f"🎲 {char.name} 进行【{req.skill}】检定 (DC {req.dc})："
            f"d20={result['d20']} {'+' if result['modifier']>=0 else ''}{result['modifier']}"
            f" = **{result['total']}** → "
            f"{'✅ 成功' if result['success'] else '❌ 失败'}"
            f"{' [已熟练]' if result['proficient'] else ' [未熟练]'}"
        ),
        log_type    = "dice",
        dice_result = result,
    ))
    await db.commit()
    return result


# ── 战役日志 ──────────────────────────────────────────────

@router.post("/sessions/{session_id}/journal")
async def generate_journal(session_id: str, db: AsyncSession = Depends(get_db)):
    """生成本次冒险的叙事日志摘要（调用 DM Agent Chatflow，独立新对话）"""
    session = await get_session_or_404(session_id, db)
    module  = await db.get(Module, session.module_id)

    log_result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .order_by(GameLog.created_at.asc())
        .limit(80)
    )
    logs = log_result.scalars().all()
    if not logs:
        return {"journal": "还没有冒险记录可以生成日志。"}

    log_text = "\n".join(f"[{l.role}] {l.content}" for l in logs if l.content)
    module_summary = (module.parsed_content or {}).get("plot_summary", "") if module else ""

    try:
        from services.llm import get_llm
        from langchain_core.messages import SystemMessage as _SM, HumanMessage as _HM
        llm = get_llm(temperature=0.8, max_tokens=800)
        resp = await llm.ainvoke([
            _SM(content="你是一位文笔出众的 DnD 5e 编年史作者，擅长将冒险记录改写为史诗般的战役日志。"),
            _HM(content=(
                f"## 模组背景\n{module_summary}\n\n"
                f"## 冒险记录\n{log_text[-3000:]}\n\n"
                "请以第三人称叙事风格，为这段冒险旅程写一篇简短的战役日志（300字左右）。"
                "包含：英雄们的行动、遭遇的危险、关键事件和转折。"
                "语气史诗而充满感情，像一部奇幻小说的章节摘要。"
                "直接输出日志正文，不要有任何前缀、标签或JSON格式。"
            )),
        ])
        journal_text = resp.content.strip()
        if not journal_text or len(journal_text) < 20:
            journal_text = "日志生成失败"
    except Exception as e:
        journal_text = f"（AI日志生成失败：{e}）\n\n以下为原始记录节选：\n\n{log_text[:800]}"

    state = dict(session.game_state or {})
    state["last_journal"] = journal_text
    session.game_state = state; flag_modified(session, "game_state"); flag_modified(session, "game_state")
    await db.commit()

    return {"journal": journal_text, "log_count": len(logs)}


# ── 战役档案存档（Checkpoint）────────────────────────────

@router.post("/sessions/{session_id}/checkpoint")
async def save_checkpoint(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    将当前会话的冒险记录压缩为结构化 Campaign State JSON 并存档。
    - 只提取叙事/队友日志（过滤骰子、系统消息）
    - 新状态与历史档案增量合并（不覆盖已有内容）
    - 下次游戏时 player_action 会自动使用此档案作为长期记忆
    """
    session = await get_session_or_404(session_id, db)
    module  = await db.get(Module, session.module_id)

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

    log_text       = "\n".join(f"[{l.role}] {l.content}" for l in logs if l.content)
    module_summary = (module.parsed_content or {}).get("plot_summary", "") if module else ""

    try:
        new_campaign_state = await dify_client.generate_campaign_state(
            log_text       = log_text[-4000:],
            module_summary = module_summary,
            existing_state = session.campaign_state or {},
        )
    except Exception as e:
        raise HTTPException(502, f"档案生成失败: {e}")

    session.campaign_state = new_campaign_state
    await db.commit()
    return {"ok": True, "campaign_state": new_campaign_state}


@router.get("/sessions/{session_id}/checkpoint")
async def get_checkpoint(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取当前战役档案（用于前端展示存档详情）"""
    session = await get_session_or_404(session_id, db)
    return {
        "session_id":    session_id,
        "campaign_state": session.campaign_state or {},
        "has_checkpoint": session.campaign_state is not None,
    }


# ── 休息（长休 / 短休）───────────────────────────────────

@router.post("/sessions/{session_id}/rest", response_model=RestResponse)
async def take_rest(
    session_id: str,
    rest_type:  str = "long",   # "long" | "short"
    db: AsyncSession = Depends(get_db),
):
    """
    长休 (long)：HP满值、法术位全部恢复、清除条件与专注
    短休 (short)：消耗一颗生命骰恢复HP；魔契者短休恢复法术位
    """
    if rest_type not in ("long", "short"):
        raise HTTPException(400, "rest_type 必须为 'long' 或 'short'")

    session = await get_session_or_404(session_id, db)
    state   = session.game_state or {}

    roster    = CharacterRoster(db, session)
    all_chars = await roster.party()
    results   = []

    for char in all_chars:
        derived   = char.derived or {}
        hp_max    = derived.get("hp_max", char.hp_current)
        hit_die   = derived.get("hit_die", 8)
        con_mod   = derived.get("ability_modifiers", {}).get("con", 0)
        caster_t  = derived.get("caster_type")
        slots_max = dict(derived.get("spell_slots_max", {}))
        cls_key   = _normalize_class(char.char_class)

        old_hp = char.hp_current

        # Initialize hit_dice_remaining if not set
        if char.hit_dice_remaining is None:
            char.hit_dice_remaining = char.level

        if rest_type == "long":
            char.hp_current    = hp_max
            char.spell_slots   = slots_max
            char.conditions    = []
            char.concentration = None
            # Long rest restores half of total hit dice (minimum 1)
            restored_dice = max(1, char.level // 2)
            char.hit_dice_remaining = min(char.level, (char.hit_dice_remaining or 0) + restored_dice)
            # Reset class resources
            char.class_resources = get_class_resource_defaults(cls_key, char.level, subclass=char.subclass)
            results.append({
                "name":              char.name,
                "hp_recovered":      hp_max - old_hp,
                "hp_current":        hp_max,
                "slots_restored":    slots_max,
                "hit_dice_remaining": char.hit_dice_remaining,
            })

        else:  # short rest
            # Check if hit dice available
            hd_remaining = char.hit_dice_remaining or 0
            hit_roll_result = None
            heal_amt = 0

            if hd_remaining > 0:
                # 消耗一颗生命骰 + CON 调整值
                hit_roll = roll_dice(f"1d{hit_die}")
                heal_amt = max(1, hit_roll["total"] + con_mod)
                char.hp_current = min(hp_max, char.hp_current + heal_amt)
                char.hit_dice_remaining = hd_remaining - 1
                hit_roll_result = hit_roll["rolls"][0]
            else:
                heal_amt = 0

            # 魔契者短休恢复法术位
            if caster_t == "pact":
                char.spell_slots = slots_max

            # ── 短休资源恢复 ──
            cls_key_sr = _normalize_class(char.char_class)
            class_res_sr = dict(char.class_resources or {})
            changed = False

            # Fighter: Second Wind + Action Surge reset
            if cls_key_sr == "Fighter":
                class_res_sr["second_wind_used"] = False
                if char.level >= 2:
                    class_res_sr["action_surge_used"] = False
                # Battle Master: Superiority Dice reset
                sub_eff = (char.derived or {}).get("subclass_effects", {})
                if sub_eff.get("battle_master"):
                    sd_max = sub_eff.get("superiority_dice_max", 4)
                    class_res_sr["superiority_dice_remaining"] = sd_max
                changed = True

            # Monk: Ki Points reset to max
            elif cls_key_sr == "Monk" and char.level >= 2:
                ki_max = (char.derived or {}).get("subclass_effects", {}).get("ki_max", char.level)
                class_res_sr["ki_remaining"] = ki_max
                changed = True

            # Bard: Bardic Inspiration reset (only at level 5+ with Font of Inspiration)
            elif cls_key_sr == "Bard" and char.level >= 5:
                cha_mod = (char.derived or {}).get("ability_modifiers", {}).get("cha", 3)
                class_res_sr["bardic_inspiration_remaining"] = max(1, cha_mod)
                changed = True

            # Cleric: Channel Divinity reset
            elif cls_key_sr == "Cleric":
                class_res_sr["channel_divinity_used"] = False
                changed = True

            # Paladin: Channel Divinity reset
            elif cls_key_sr == "Paladin":
                class_res_sr["channel_divinity_used"] = False
                changed = True

            # Druid: Wild Shape uses do NOT reset on short rest (only long rest)
            # But Circle of Land: Natural Recovery (recover spell slots)
            elif cls_key_sr == "Druid":
                sub_eff = (char.derived or {}).get("subclass_effects", {})
                if sub_eff.get("circle_of_land") and sub_eff.get("natural_recovery"):
                    # Recover spell slots up to half druid level (rounded up)
                    max_slot_level = (char.level + 1) // 2
                    slots_max_dr = (char.derived or {}).get("spell_slots_max", {})
                    current_slots_dr = dict(char.spell_slots or {})
                    recovery_budget = (char.level + 1) // 2  # total slot levels to recover
                    for lv in range(1, min(max_slot_level + 1, 6)):
                        sk = ["1st","2nd","3rd","4th","5th"][lv-1]
                        cap = slots_max_dr.get(sk, 0)
                        cur = current_slots_dr.get(sk, 0)
                        if cur < cap and recovery_budget >= lv:
                            current_slots_dr[sk] = cur + 1
                            recovery_budget -= lv
                    char.spell_slots = current_slots_dr
                changed = True

            if changed:
                char.class_resources = class_res_sr

            results.append({
                "name":              char.name,
                "hit_die_roll":      hit_roll_result,
                "con_mod":           con_mod,
                "hp_recovered":      char.hp_current - old_hp,
                "hp_current":        char.hp_current,
                "slots_restored":    slots_max if caster_t == "pact" else {},
                "hit_dice_remaining": char.hit_dice_remaining,
                "no_hit_dice":       hd_remaining <= 0,
                "class_resources":   class_res_sr if changed else None,
            })

    rest_label = "长休" if rest_type == "long" else "短休"
    db.add(GameLog(
        session_id = session_id,
        role       = "system",
        content    = (f"🌙 队伍完成了{rest_label}。"
                      + ("HP和法术位已完全恢复。" if rest_type == "long" else "消耗了一颗生命骰。")),
        log_type   = "system",
    ))
    await db.commit()

    return {
        "rest_type":  rest_type,
        "characters": results,
    }


# ── 内部辅助 ──────────────────────────────────────────────

def _build_enemy_from_module(monster: dict) -> dict:
    """
    将 WF1 解析出的怪物 stat block 转换为战斗用 EnemyState 格式。
    WF1 v0.3 已输出完整 ability_scores / actions，直接使用。
    """
    scores = monster.get("ability_scores", {})

    def mod(s): return (s - 10) // 2

    str_mod = mod(scores.get("str", 10))
    dex_mod = mod(scores.get("dex", 10))
    con_mod = mod(scores.get("con", 10))

    # 主攻击行动（取第一个 melee/ranged attack）
    primary_action = next(
        (a for a in monster.get("actions", [])
         if a.get("type") in ("melee_attack", "ranged_attack")),
        None,
    )
    attack_bonus  = primary_action.get("attack_bonus", 3) if primary_action else 3
    damage_dice   = primary_action.get("damage_dice", "1d6+2") if primary_action else "1d6+2"
    damage_type   = primary_action.get("damage_type", "钝击") if primary_action else "钝击"

    hp = monster.get("hp", 10)

    return {
        "id":           f"enemy_{uuid.uuid4().hex[:8]}",
        "name":         monster.get("name", "未知怪物"),
        "hp_current":   hp,
        "hp_max":       hp,
        "ac":           monster.get("ac", 13),
        "conditions":   [],
        "dead":         False,
        # 战斗计算用
        "ability_scores": scores,
        "attack_bonus": attack_bonus,
        "damage_dice":  damage_dice,
        "damage_type":  damage_type,
        "speed":        monster.get("speed", 30),
        "resistances":  monster.get("resistances", []),
        "immunities":   monster.get("immunities", []),
        "special_abilities": monster.get("special_abilities", []),
        "actions":      monster.get("actions", []),
        "tactics":      monster.get("tactics", "直接攻击最近的目标"),
        # 先攻用
        "initiative":   dex_mod,
        "is_player":    False,
        # 衍生属性快照（供 ContextBuilder 注入 game_state）
        "derived": {
            "hp_max":           hp,
            "ac":               monster.get("ac", 13),
            "initiative":       dex_mod,
            "attack_bonus":     attack_bonus,
            "ability_modifiers": {
                "str": str_mod, "dex": dex_mod, "con": con_mod,
                "int": mod(scores.get("int", 10)),
                "wis": mod(scores.get("wis", 10)),
                "cha": mod(scores.get("cha", 10)),
            },
        },
    }


async def _init_combat(
    session:         Session,
    initial_enemies: list,
    characters:      list[Character],
    module:          Module,
    db:              AsyncSession,
) -> None:
    """
    初始化战斗状态。

    优先级：
      1. DM Agent 在 state_delta.initial_enemies 中指定的敌人（包含名称/HP等）
      2. 回退：从 Module.parsed_content.monsters 取前3个（使用 WF1 完整 stat block）
      3. 最终回退：生成一个默认敌对生物
    """
    enemies: list[dict] = []

    if initial_enemies:
        # DM Agent 指定了敌人，用模组数据填充完整 stat block
        parsed_monsters = {
            m["name"]: m
            for m in (module.parsed_content or {}).get("monsters", [])
        }
        for ie in initial_enemies:
            # DM 有时返回字符串列表 ["骷髅", "骷髅"] 而非 dict 列表
            if isinstance(ie, str):
                ie = {"name": ie}
            name = ie.get("name", "未知怪物") if isinstance(ie, dict) else str(ie)
            base = parsed_monsters.get(name)
            if base:
                enemy = _build_enemy_from_module(base)
                # 允许 DM 覆盖 HP（如场景中出现受伤怪物）
                if isinstance(ie, dict) and ie.get("hp_current"):
                    enemy["hp_current"] = ie["hp_current"]
            else:
                # 模组中没有这个怪物，用 DM 给的基础信息
                enemy = {
                    "id":         f"enemy_{uuid.uuid4().hex[:8]}",
                    "name":       name,
                    "hp_current": ie.get("hp", 20) if isinstance(ie, dict) else 20,
                    "hp_max":     ie.get("hp", 20) if isinstance(ie, dict) else 20,
                    "ac":         ie.get("ac", 13) if isinstance(ie, dict) else 13,
                    "conditions": [],
                    "dead":       False,
                    "attack_bonus": ie.get("attack_bonus", 3),
                    "damage_dice":  ie.get("damage_dice", "1d6+2"),
                    "tactics":    "直接攻击最近的目标",
                    "is_player":  False,
                    "initiative": 0,
                    "derived":    {"hp_max": ie.get("hp", 20), "ac": ie.get("ac", 13),
                                   "attack_bonus": ie.get("attack_bonus", 3)},
                }
            enemies.append(enemy)

    if not enemies:
        # 回退：使用模组怪物（WF1 完整 stat block）
        module_monsters = (module.parsed_content or {}).get("monsters", [])
        for m in module_monsters[:3]:
            enemies.append(_build_enemy_from_module(m))

    if not enemies:
        # 最终回退：通用敌对生物
        enemies.append({
            "id": f"enemy_{uuid.uuid4().hex[:8]}",
            "name": "敌对生物",
            "hp_current": 30, "hp_max": 30, "ac": 13,
            "conditions": [], "dead": False,
            "attack_bonus": 4, "damage_dice": "1d8+2", "damage_type": "钝击",
            "tactics": "直接攻击最近的目标",
            "is_player": False, "initiative": 1,
            "derived": {"hp_max": 30, "ac": 13, "attack_bonus": 4,
                        "ability_modifiers": {"str":2,"dex":1,"con":1,"int":-1,"wis":0,"cha":-1}},
        })

    # 掷先攻（角色 + 敌人）
    # 确保每个敌人都有 is_enemy 标记
    for e in enemies:
        e["is_enemy"] = True
        e.setdefault("is_player", False)

    combatants = [
        {"id": str(c.id), "name": c.name,
         "initiative": (c.derived or {}).get("initiative", 0),
         "is_player": c.is_player, "is_enemy": False}
        for c in characters
    ] + enemies
    initiative_order = roll_initiative(combatants)

    # 初始站位（角色左侧，敌人右侧）
    positions = {}
    for i, c in enumerate(characters):
        positions[str(c.id)] = {"x": 2, "y": 3 + i}
    for i, e in enumerate(enemies):
        positions[e["id"]] = {"x": 17, "y": 8 + i}

    # 清理旧战斗状态（防止残留导致 MultipleResultsFound）
    old_combats = await db.execute(select(CombatState).where(CombatState.session_id == session.id))
    for old in old_combats.scalars().all():
        await db.delete(old)

    combat = CombatState(
        session_id         = session.id,
        grid_data          = {},
        entity_positions   = positions,
        turn_order         = initiative_order,
        current_turn_index = 0,
        round_number       = 1,
    )
    db.add(combat)
    session.combat_active = True

    state            = dict(session.game_state or {})
    state["enemies"] = enemies
    session.game_state = state; flag_modified(session, "game_state")
    await db.flush()
