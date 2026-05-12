"""多人联机房间业务逻辑

职责：
- 房间码生成（避免易混淆字符 0/O/1/I）
- 创建/加入/离开/解散房间
- 成员管理（角色认领、踢人、转让房主）
- 在线状态判断（基于 last_seen_at 心跳）

不负责：
- WebSocket 广播（由 ws_manager 处理）
- 战斗权限校验（由 combat 端点中间件处理）
"""
import random
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import Session, Character, SessionMember, User, Module


# ── 常量 ─────────────────────────────────────────────

ROOM_CODE_CHARS = "23456789"  # 8进制，去掉 0/1 易混字符
ROOM_CODE_LENGTH = 6
OFFLINE_THRESHOLD_SECONDS = 30  # 超过 30s 无心跳 → 视为离线 → AI 托管
MAX_CODE_GEN_ATTEMPTS = 20
DEFAULT_GROUP_ID = "main"
DEFAULT_GROUP_NAME = "主队"
DEFAULT_GROUP_LOCATION = "当前场景"
READINESS_STATUSES = {"drafting", "ready", "waiting"}


# ── 房间码生成 ───────────────────────────────────────

async def generate_unique_room_code(db: AsyncSession) -> str:
    """生成 6 位数字房间码，确保数据库内唯一。"""
    for _ in range(MAX_CODE_GEN_ATTEMPTS):
        code = "".join(random.choices(ROOM_CODE_CHARS, k=ROOM_CODE_LENGTH))
        existing = await db.execute(
            select(Session.id).where(Session.room_code == code)
        )
        if existing.scalar_one_or_none() is None:
            return code
    raise HTTPException(500, "房间码生成失败，请重试")


# ── 创建/加入/离开 ───────────────────────────────────

async def create_room(
    db: AsyncSession,
    user_id: str,
    module_id: str,
    save_name: Optional[str],
    max_players: int,
) -> Session:
    """创建多人房间。创建者自动成为 host。"""
    # 验证模组存在
    from models import Module
    module = await db.get(Module, module_id)
    if not module:
        raise HTTPException(404, "模组不存在")

    code = await generate_unique_room_code(db)
    session = Session(
        user_id=user_id,
        module_id=module_id,
        save_name=save_name or f"多人房间 {code}",
        is_multiplayer=True,
        room_code=code,
        host_user_id=user_id,
        max_players=max_players,
        game_state={"multiplayer": {"current_speaker_user_id": None,
                                     "speak_round": 0,
                                     "pending_actions": [],
                                     "online_user_ids": [user_id],
                                     "active_group_id": DEFAULT_GROUP_ID,
                                     "party_groups": [{
                                         "id": DEFAULT_GROUP_ID,
                                         "name": DEFAULT_GROUP_NAME,
                                         "location": DEFAULT_GROUP_LOCATION,
                                         "member_user_ids": [user_id],
                                     }],
                                     "pending_actions_by_group": {DEFAULT_GROUP_ID: []},
                                     "group_readiness": {DEFAULT_GROUP_ID: {}}}},
    )
    db.add(session)
    await db.flush()  # 拿到 session.id

    host_member = SessionMember(
        session_id=session.id,
        user_id=user_id,
        role="host",
    )
    db.add(host_member)
    await db.commit()
    await db.refresh(session)
    return session


async def join_room(
    db: AsyncSession,
    user_id: str,
    room_code: str,
) -> Tuple[Session, SessionMember]:
    """通过房间码加入房间。游戏未开始 + 房间未满 才允许加入。"""
    result = await db.execute(
        select(Session).where(Session.room_code == room_code)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "房间码无效")
    if not session.is_multiplayer:
        raise HTTPException(400, "该房间不是多人房间")
    if _is_game_started(session):
        raise HTTPException(409, "游戏已经开始，无法加入")

    # 检查是否已在房间中
    existing = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session.id,
            SessionMember.user_id == user_id,
        )
    )
    member = existing.scalar_one_or_none()
    if member:
        # 已在房间，刷新 last_seen 当作"重连"
        member.last_seen_at = datetime.utcnow()
        await db.commit()
        await db.refresh(member)
        return session, member

    # 检查房间容量
    members_count = await _count_members(db, session.id)
    if members_count >= session.max_players:
        raise HTTPException(409, "房间已满")

    member = SessionMember(
        session_id=session.id,
        user_id=user_id,
        role="player",
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return session, member


async def leave_room(
    db: AsyncSession,
    user_id: str,
    session_id: str,
) -> dict:
    """离开房间。

    - 房主离开 + 还有其他成员 → 自动转让给最早加入的成员
    - 房主离开 + 没有其他成员 → 解散房间（清理 session_members，session 保留以归档）
    - 普通成员离开 → 仅删除 SessionMember 记录；其角色会变为 NPC（is_player=False）
    """
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")

    member = await _get_member(db, session.id, user_id)
    if not member:
        raise HTTPException(404, "你不在该房间中")

    is_host = member.role == "host"

    # 删除该成员
    if member.character_id:
        # 真人角色降级为 AI 托管（is_player=False，user_id 清空）
        char = await db.get(Character, member.character_id)
        if char:
            char.user_id = None
            char.is_player = False
    await db.delete(member)
    await db.flush()

    if is_host:
        # 找下一位最早加入者作为新 host
        result = await db.execute(
            select(SessionMember)
            .where(SessionMember.session_id == session.id)
            .order_by(SessionMember.joined_at.asc())
        )
        new_host = result.scalars().first()
        if new_host:
            new_host.role = "host"
            session.host_user_id = new_host.user_id
            transfer_to = new_host.user_id
        else:
            # 房间空了，归档：room_code 失效，保留 session 数据
            session.room_code = None
            transfer_to = None
        await db.commit()
        return {"left": user_id, "host_transferred_to": transfer_to,
                "room_dissolved": transfer_to is None}

    await db.commit()
    return {"left": user_id, "host_transferred_to": None, "room_dissolved": False}


# ── 角色认领/踢人/转让 ───────────────────────────────

async def claim_character(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    character_id: str,
) -> SessionMember:
    """
    认领（或接管）一个角色。允许的场景：

      1) 我自己的角色（重连续玩 / 换角色）—— 直接绑回
      2) "孤儿"角色（session_id 为 None）—— 刚从多人向导创建完，第一次绑
      3) 房间内的 AI 角色（is_player=False）—— 接管：fill_ai 生成的 / 其他玩家
         离开后降级的 / 长时间断线被托管的，都允许在线玩家拿回来玩

    拒绝的场景：
      - 角色属于别的 session
      - 角色已被**别的活跃 SessionMember** 绑（在线 / 离线但还没触发 leave）
        → 此时其他玩家有"占有权"，本玩家不能强抢；想抢的话需要房主先 kick

    历史上这里硬性 `is_player=True` 的限制把"接管 AI / 接管离线队友"两个
    合理需求都堵死了 —— 用户反馈过"断线重连不能接管人机"。
    """
    member = await _get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")
    if char.session_id is not None and char.session_id != session_id:
        raise HTTPException(404, "角色不属于该房间")

    # 检查是否已被**其他**真实成员持有
    # 注意：拿 SessionMember 判而不是 char.is_player —— is_player 是"当前是否真人控"，
    # SessionMember.character_id 才是"占有权"
    existing = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session_id,
            SessionMember.character_id == character_id,
        )
    )
    other = existing.scalar_one_or_none()
    if other and other.user_id != user_id:
        raise HTTPException(409, "该角色已被其他玩家认领")

    # 如果该玩家之前 claim 过别的角色，先把那个角色降级为 AI（防止脚踩两条船）
    if member.character_id and member.character_id != character_id:
        prev = await db.get(Character, member.character_id)
        if prev:
            prev.user_id = None
            prev.is_player = False

    member.character_id = character_id
    char.user_id = user_id
    char.is_player = True       # 接管 → 升级为真人控
    char.session_id = session_id   # 孤儿角色顺带绑定到房间
    await db.commit()
    await db.refresh(member)
    return member


async def kick_member(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
    target_user_id: str,
) -> dict:
    """房主踢人。"""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以踢人")
    if target_user_id == actor_user_id:
        raise HTTPException(400, "不能踢出自己，请使用离开房间")

    target = await _get_member(db, session_id, target_user_id)
    if not target:
        raise HTTPException(404, "目标成员不在房间中")

    if target.character_id:
        char = await db.get(Character, target.character_id)
        if char:
            char.user_id = None
            char.is_player = False

    await db.delete(target)
    await db.commit()
    return {"kicked": target_user_id}


async def transfer_host(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
    new_host_user_id: str,
) -> dict:
    """转让房主权限。"""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以转让")

    actor = await _get_member(db, session_id, actor_user_id)
    target = await _get_member(db, session_id, new_host_user_id)
    if not target:
        raise HTTPException(404, "目标成员不在房间中")
    if actor.user_id == target.user_id:
        raise HTTPException(400, "目标已是房主")

    actor.role = "player"
    target.role = "host"
    session.host_user_id = new_host_user_id
    await db.commit()
    return {"new_host_user_id": new_host_user_id}


# ── 开始游戏 ─────────────────────────────────────────

async def start_game(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
) -> Session:
    """房主开始游戏。

    要求：
    - 至少 1 名成员已认领角色（其余空位将由 AI 托管）
    - 游戏尚未开始
    """
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以开始游戏")
    if _is_game_started(session):
        raise HTTPException(409, "游戏已经开始")

    members = await _list_members_raw(db, session_id)
    claimed = [m for m in members if m.character_id]
    if not claimed:
        raise HTTPException(400, "至少需要一位玩家认领角色才能开始")

    # ── 首次启动：绑定主角色 + 生成开场白 ──
    # 单人模式的 /game/sessions POST 里会做这两件事，多人之前漏了，
    # 导致玩家进入 Adventure 页看到空页。
    from models import GameLog
    already_started = bool(session.current_scene)  # 若已有 current_scene，说明之前启动过，仅刷新状态

    if not already_started:
        # 1. 绑定 session.player_character_id = 第一位 claimed（便于单人场景代码复用）
        if not session.player_character_id:
            session.player_character_id = claimed[0].character_id

        # 2. 生成开场白（复用单人模式的 _generate_opening）
        module = await db.get(Module, session.module_id)
        parsed = (module.parsed_content or {}) if module else {}
        scenes = parsed.get("scenes", []) or []
        raw_scene = scenes[0]["description"] if scenes and isinstance(scenes[0], dict) else ""
        try:
            from api.game import _generate_opening  # lazy import 避免循环依赖
            first_scene = await _generate_opening(parsed, raw_scene)
        except Exception:
            first_scene = raw_scene or "冒险正在开始……"

        session.current_scene = first_scene

        # 3. 写入 [开场] GameLog
        db.add(GameLog(
            session_id=session_id,
            role="dm",
            content=f"[开场] {first_scene}",
            log_type="narrative",
        ))

    # 标记游戏已开始：在 game_state 写一个 flag
    state = session.game_state or {}
    mp = state.setdefault("multiplayer", {})
    mp["game_started"] = True
    mp["online_user_ids"] = [m.user_id for m in members]
    # 初始发言者：第一位 claimed 玩家
    mp["current_speaker_user_id"] = claimed[0].user_id
    mp["speak_round"] = 1
    mp["pending_actions"] = []
    session.game_state = state
    flag_modified(session, "game_state")

    await db.commit()
    await db.refresh(session)
    return session


# ── 补满 AI 队友 ─────────────────────────────────────

async def list_ai_companions(
    db: AsyncSession,
    session_id: str,
) -> List[dict]:
    """列出该房间的 AI 队友（session_id 匹配 + is_player=False）。"""
    result = await db.execute(
        select(Character)
        .where(Character.session_id == session_id, Character.is_player == False)
        .order_by(Character.id.asc())
    )
    out = []
    for c in result.scalars().all():
        out.append({
            "id": c.id,
            "name": c.name,
            "race": c.race,
            "char_class": c.char_class,
            "level": c.level,
            "hp_max": (c.derived or {}).get("hp_max"),
        })
    return out


async def fill_with_ai_companions(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
) -> dict:
    """房主触发：根据 max_players 与已认领人数差额，生成 AI 队友补位。

    要求：
    - 房主权限
    - 游戏未开始
    - 至少 1 名成员已认领角色（以其作为 party 生成参考）

    返回：{"generated": N, "companions": [...], "already_full": bool}
    """
    # 延迟导入，避免循环依赖（services 模块之间）
    from services.langgraph_client import langgraph_client
    from services.dnd_rules import (
        apply_racial_bonuses, calc_derived,
        CLASS_SAVE_PROFICIENCIES, CLASS_SKILL_CHOICES,
    )

    # 与 characters.py 中 generate_party 使用相同的技能池与规范化
    try:
        from api.characters import ALL_SKILLS, _normalize_class
    except Exception:
        # 回退：简化版
        ALL_SKILLS = []
        def _normalize_class(c: str) -> str:
            return c or "Fighter"

    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以补 AI 队友")
    if _is_game_started(session):
        raise HTTPException(409, "游戏已经开始，无法补位")

    members = await _list_members_raw(db, session_id)
    claimed = [m for m in members if m.character_id]
    if not claimed:
        raise HTTPException(400, "至少需要一位玩家创建并认领角色作为参考")

    existing_ai = await list_ai_companions(db, session_id)
    target_total = session.max_players or 4
    need = target_total - len(claimed) - len(existing_ai)
    if need <= 0:
        return {"generated": 0, "companions": existing_ai, "already_full": True}

    # 取第一位已认领角色作为 party 生成参考
    ref_char = await db.get(Character, claimed[0].character_id)
    if not ref_char:
        raise HTTPException(500, "参考角色加载失败")

    module = await db.get(Module, session.module_id)
    if not module:
        raise HTTPException(404, "模组不存在")

    companions_data = await langgraph_client.generate_party(
        player_class=ref_char.char_class,
        player_race=ref_char.race,
        player_level=ref_char.level,
        party_size=need,
        module_data=module.parsed_content or {},
    )

    new_ids = []
    for c in companions_data[:need]:
        base_scores = c.get("ability_scores", {
            "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10,
        })
        companion_race = c.get("race", "人类")
        companion_class = c.get("class", "Fighter")
        companion_level = c.get("level", ref_char.level)

        final_scores = apply_racial_bonuses(base_scores, companion_race)
        cls_key = _normalize_class(companion_class)
        save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])
        ai_skills = c.get("proficient_skills", [])
        skill_config = CLASS_SKILL_CHOICES.get(cls_key, {"count": 2, "options": ALL_SKILLS})
        if not ai_skills:
            ai_skills = (skill_config["options"] or [])[:skill_config["count"]]

        derived = calc_derived(
            companion_class, companion_level, final_scores, c.get("subclass"),
            race=companion_race, proficient_skills=ai_skills,
        )
        spell_slots = dict(derived.get("spell_slots_max", {}))

        companion = Character(
            session_id=session_id,
            is_player=False,
            user_id=None,
            name=c.get("name", "未知冒险者"),
            race=companion_race,
            char_class=companion_class,
            subclass=c.get("subclass"),
            level=companion_level,
            background=c.get("background"),
            alignment=c.get("alignment", "中立善良"),
            ability_scores=final_scores,
            derived=derived,
            hp_current=derived["hp_max"],
            spell_slots=spell_slots,
            known_spells=c.get("known_spells", []),
            cantrips=c.get("cantrips", []),
            proficient_skills=ai_skills,
            proficient_saves=save_profs,
            personality=c.get("personality_traits", ""),
            speech_style=c.get("speech_style", ""),
            combat_preference=c.get("combat_preference", ""),
            backstory=c.get("backstory", ""),
            catchphrase=c.get("catchphrase", ""),
        )
        db.add(companion)
        await db.flush()
        new_ids.append(companion.id)

    await db.commit()
    companions = await list_ai_companions(db, session_id)
    return {"generated": len(new_ids), "companions": companions, "already_full": False}


# ── 查询 ─────────────────────────────────────────────

async def list_members(
    db: AsyncSession,
    session_id: str,
) -> List[dict]:
    """返回成员列表，包含 user 信息、character 名称、在线状态。"""
    rows = await db.execute(
        select(SessionMember, User, Character)
        .join(User, User.id == SessionMember.user_id)
        .outerjoin(Character, Character.id == SessionMember.character_id)
        .where(SessionMember.session_id == session_id)
        .order_by(SessionMember.joined_at.asc())
    )
    out = []
    now = datetime.utcnow()
    threshold = now - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
    for member, user, char in rows.all():
        seconds_since_seen = None
        if member.last_seen_at is not None:
            seconds_since_seen = max(0, int((now - member.last_seen_at).total_seconds()))
        out.append({
            "user_id": member.user_id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": member.role,
            "character_id": member.character_id,
            "character_name": char.name if char else None,
            "is_online": member.last_seen_at is not None and member.last_seen_at >= threshold,
            "seconds_since_seen": seconds_since_seen,
            "joined_at": member.joined_at,
        })
    return out


async def get_room_info(
    db: AsyncSession,
    session_id: str,
) -> dict:
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    mp_state = await ensure_multiplayer_state(db, session_id)
    members = await list_members(db, session_id)
    ai_companions = await list_ai_companions(db, session_id)
    mp = (session.game_state or {}).get("multiplayer", {})
    return {
        "session_id": session.id,
        "room_code": session.room_code,
        "module_id": session.module_id,
        "save_name": session.save_name,
        "host_user_id": session.host_user_id,
        "max_players": session.max_players,
        "is_multiplayer": session.is_multiplayer,
        "game_started": _is_game_started(session),
        "members": members,
        "ai_companions": ai_companions,
        "current_speaker_user_id": mp.get("current_speaker_user_id"),
        "speak_round": mp.get("speak_round", 0),
        "party_groups": mp_state["party_groups"],
        "active_group_id": mp_state["active_group_id"],
        "pending_actions_by_group": mp_state["pending_actions_by_group"],
        "group_readiness": mp_state["group_readiness"],
        "created_at": session.created_at,
    }


# ── 探索分队 / 行动队列 ─────────────────────────────────

async def ensure_multiplayer_state(
    db: AsyncSession,
    session_id: str,
) -> dict:
    """归一化多人探索状态，并返回 multiplayer 子状态。

    第一阶段只维护探索层的轻量分队：
    - `party_groups`：每个分队的名字、位置和成员 user_id。
    - `active_group_id`：当前焦点分队。
    - `pending_actions_by_group`：每个分队的待处理行动意图。
    """
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")

    members = await _list_members_raw(db, session_id)
    member_ids = [member.user_id for member in members]
    member_id_set = set(member_ids)

    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    groups = _normalize_party_groups(mp.get("party_groups"), member_ids)
    pending = _normalize_group_actions(mp.get("pending_actions_by_group"), groups)
    readiness = _normalize_group_readiness(mp.get("group_readiness"), groups, member_id_set)

    active_group_id = mp.get("active_group_id") or DEFAULT_GROUP_ID
    if active_group_id not in {group["id"] for group in groups}:
        active_group_id = groups[0]["id"] if groups else DEFAULT_GROUP_ID

    mp["party_groups"] = groups
    mp["active_group_id"] = active_group_id
    mp["pending_actions_by_group"] = pending
    mp["group_readiness"] = readiness
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return {
        "party_groups": groups,
        "active_group_id": active_group_id,
        "pending_actions_by_group": pending,
        "group_readiness": readiness,
    }


async def set_member_group(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    group_name: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    """把当前用户移动到指定探索分队；分队不存在时创建。"""
    member = await _get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")

    clean_group_id = _clean_group_id(group_id)
    clean_name = (group_name or "").strip() or (DEFAULT_GROUP_NAME if clean_group_id == DEFAULT_GROUP_ID else clean_group_id)
    clean_location = (location or "").strip() or DEFAULT_GROUP_LOCATION

    await ensure_multiplayer_state(db, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    groups = list(mp.get("party_groups") or [])
    pending = dict(mp.get("pending_actions_by_group") or {})
    readiness = dict(mp.get("group_readiness") or {})

    target = None
    for group in groups:
        group["member_user_ids"] = [
            uid for uid in group.get("member_user_ids", [])
            if uid != user_id
        ]
        if group.get("id") == clean_group_id:
            target = group

    if target is None:
        target = {
            "id": clean_group_id,
            "name": clean_name,
            "location": clean_location,
            "member_user_ids": [],
        }
        groups.append(target)
    else:
        target["name"] = clean_name
        target["location"] = clean_location

    target["member_user_ids"] = _unique_preserve_order([
        *target.get("member_user_ids", []),
        user_id,
    ])
    groups = _drop_empty_non_default_groups(groups)
    pending.setdefault(clean_group_id, [])

    mp["party_groups"] = groups
    mp["pending_actions_by_group"] = {
        group["id"]: list(pending.get(group["id"], []))
        for group in groups
    }
    mp["group_readiness"] = {
        group["id"]: {
            uid: status
            for uid, status in dict(readiness.get(group["id"], {})).items()
            if uid in (group.get("member_user_ids") or [])
        }
        for group in groups
    }
    mp["group_readiness"].setdefault(clean_group_id, {})
    mp["group_readiness"][clean_group_id][user_id] = "drafting"
    mp["active_group_id"] = clean_group_id
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return await get_room_info(db, session_id)


async def submit_group_action(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    action_text: str,
) -> dict:
    """提交一条当前分队内的待处理探索行动意图。"""
    text = (action_text or "").strip()
    if not text:
        raise HTTPException(400, "行动内容不能为空")
    if len(text) > 500:
        raise HTTPException(400, "行动内容过长")

    member = await _get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    user = await db.get(User, user_id)
    clean_group_id = _clean_group_id(group_id)
    await ensure_multiplayer_state(db, session_id)

    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    groups = list(mp.get("party_groups") or [])
    group = next((item for item in groups if item.get("id") == clean_group_id), None)
    if not group:
        raise HTTPException(404, "分队不存在")
    if user_id not in (group.get("member_user_ids") or []):
        raise HTTPException(403, "你不在该分队中")

    pending = dict(mp.get("pending_actions_by_group") or {})
    readiness = dict(mp.get("group_readiness") or {})
    actions = list(pending.get(clean_group_id) or [])
    actions.append({
        "user_id": user_id,
        "display_name": (user.display_name or user.username) if user else user_id,
        "text": text,
        "created_at": datetime.utcnow().isoformat(),
    })
    pending[clean_group_id] = actions[-20:]
    group_readiness = dict(readiness.get(clean_group_id) or {})
    group_readiness[user_id] = "drafting"
    readiness[clean_group_id] = group_readiness

    mp["pending_actions_by_group"] = pending
    mp["group_readiness"] = readiness
    mp["active_group_id"] = clean_group_id
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return await get_room_info(db, session_id)


async def set_group_readiness(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    status: str,
) -> dict:
    """标记当前用户在分队内的桌面准备状态。"""
    clean_status = (status or "").strip().lower()
    if clean_status not in READINESS_STATUSES:
        raise HTTPException(400, "无效的分队准备状态")

    member = await _get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")

    clean_group_id = _clean_group_id(group_id)
    await ensure_multiplayer_state(db, session_id)

    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    groups = list(mp.get("party_groups") or [])
    group = next((item for item in groups if item.get("id") == clean_group_id), None)
    if not group:
        raise HTTPException(404, "分队不存在")
    if user_id not in (group.get("member_user_ids") or []):
        raise HTTPException(403, "你不在该分队中")

    readiness = dict(mp.get("group_readiness") or {})
    group_readiness = dict(readiness.get(clean_group_id) or {})
    group_readiness[user_id] = clean_status
    readiness[clean_group_id] = group_readiness

    mp["group_readiness"] = readiness
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return await get_room_info(db, session_id)


async def set_active_group(
    db: AsyncSession,
    session_id: str,
    group_id: str,
    actor_user_id: Optional[str] = None,
) -> dict:
    """切换当前探索焦点分队，不移动任何成员。"""
    if actor_user_id is not None:
        member = await _get_member(db, session_id, actor_user_id)
        if not member:
            raise HTTPException(403, "你不在该房间中")

    clean_group_id = _clean_group_id(group_id)
    await ensure_multiplayer_state(db, session_id)

    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    group_ids = {group["id"] for group in mp.get("party_groups") or []}
    if clean_group_id not in group_ids:
        raise HTTPException(404, "分队不存在")

    mp["active_group_id"] = clean_group_id
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return await get_room_info(db, session_id)


async def clear_group_actions(
    db: AsyncSession,
    session_id: str,
    group_id: str,
    actor_user_id: Optional[str] = None,
) -> dict:
    """清空某个探索分队的待处理行动。"""
    if actor_user_id is not None:
        member = await _get_member(db, session_id, actor_user_id)
        if not member:
            raise HTTPException(403, "你不在该房间中")

    clean_group_id = _clean_group_id(group_id)
    await ensure_multiplayer_state(db, session_id)

    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    pending = dict(mp.get("pending_actions_by_group") or {})
    readiness = dict(mp.get("group_readiness") or {})
    pending[clean_group_id] = []
    readiness[clean_group_id] = {}

    mp["pending_actions_by_group"] = pending
    mp["group_readiness"] = readiness
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return await get_room_info(db, session_id)


# ── 心跳 ─────────────────────────────────────────────

async def update_heartbeat(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> None:
    """更新成员的 last_seen_at（由 WebSocket 心跳调用）"""
    member = await _get_member(db, session_id, user_id)
    if member:
        member.last_seen_at = datetime.utcnow()
        await db.commit()


async def mark_offline(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> None:
    """显式断开连接时立即把成员标记为离线。"""
    member = await _get_member(db, session_id, user_id)
    if member:
        member.last_seen_at = None
        await db.commit()


# ── 内部工具 ─────────────────────────────────────────

def _is_game_started(session: Session) -> bool:
    """游戏开始的判定：multiplayer.game_started 为 True，
    或者已有 current_scene/combat_active（向后兼容）"""
    state = session.game_state or {}
    if state.get("multiplayer", {}).get("game_started"):
        return True
    return bool(session.current_scene) or bool(session.combat_active)


async def _get_member(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> Optional[SessionMember]:
    result = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session_id,
            SessionMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _list_members_raw(
    db: AsyncSession,
    session_id: str,
) -> List[SessionMember]:
    result = await db.execute(
        select(SessionMember)
        .where(SessionMember.session_id == session_id)
        .order_by(SessionMember.joined_at.asc())
    )
    return list(result.scalars().all())


async def _count_members(db: AsyncSession, session_id: str) -> int:
    result = await db.execute(
        select(SessionMember).where(SessionMember.session_id == session_id)
    )
    return len(list(result.scalars().all()))


def _clean_group_id(group_id: Optional[str]) -> str:
    clean = "".join(
        ch for ch in (group_id or DEFAULT_GROUP_ID).strip().lower()
        if ch.isalnum() or ch in {"_", "-"}
    )
    return clean[:40] or DEFAULT_GROUP_ID


def _normalize_party_groups(raw_groups, member_ids: list[str]) -> list[dict]:
    member_id_set = set(member_ids)
    groups: list[dict] = []
    assigned: set[str] = set()

    if isinstance(raw_groups, list):
        for raw in raw_groups:
            if not isinstance(raw, dict):
                continue
            group_id = _clean_group_id(raw.get("id"))
            members = [
                uid for uid in _unique_preserve_order(raw.get("member_user_ids") or [])
                if uid in member_id_set and uid not in assigned
            ]
            assigned.update(members)
            groups.append({
                "id": group_id,
                "name": (raw.get("name") or (DEFAULT_GROUP_NAME if group_id == DEFAULT_GROUP_ID else group_id)).strip(),
                "location": (raw.get("location") or DEFAULT_GROUP_LOCATION).strip(),
                "member_user_ids": members,
            })

    if not groups:
        groups = [{
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }]

    main = next((group for group in groups if group["id"] == DEFAULT_GROUP_ID), None)
    if main is None:
        main = {
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }
        groups.insert(0, main)

    missing = [uid for uid in member_ids if uid not in assigned]
    main["member_user_ids"] = _unique_preserve_order([
        *main.get("member_user_ids", []),
        *missing,
    ])
    return _drop_empty_non_default_groups(groups)


def _normalize_group_actions(raw_pending, groups: list[dict]) -> dict:
    group_ids = [group["id"] for group in groups]
    pending = raw_pending if isinstance(raw_pending, dict) else {}
    normalized = {}
    for group_id in group_ids:
        actions = pending.get(group_id) if isinstance(pending, dict) else []
        normalized[group_id] = [
            action for action in (actions or [])
            if isinstance(action, dict) and action.get("text")
        ][-20:]
    return normalized


def _normalize_group_readiness(raw_readiness, groups: list[dict], member_id_set: set[str]) -> dict:
    readiness = raw_readiness if isinstance(raw_readiness, dict) else {}
    normalized = {}
    for group in groups:
        group_id = group["id"]
        member_ids = set(group.get("member_user_ids") or [])
        raw_group = readiness.get(group_id) if isinstance(readiness, dict) else {}
        if not isinstance(raw_group, dict):
            raw_group = {}
        normalized[group_id] = {
            uid: status
            for uid, status in raw_group.items()
            if uid in member_id_set
            and uid in member_ids
            and status in READINESS_STATUSES
        }
    return normalized


def _drop_empty_non_default_groups(groups: list[dict]) -> list[dict]:
    kept = [
        group for group in groups
        if group.get("id") == DEFAULT_GROUP_ID or group.get("member_user_ids")
    ]
    if not kept:
        return [{
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }]
    return kept


def _unique_preserve_order(values) -> list:
    out = []
    seen = set()
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
