"""
api.combat.class_features — combat class feature endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import get_session_or_404
from api.combat._shared import _get_ts, _save_ts, svc
from api.combat.schemas import ClassFeatureRequest
from services.combat_narrator import narrate_action
from services.dnd_rules import _normalize_class, roll_dice
from schemas.combat_responses import CombatActionResult

router = APIRouter(prefix="/game", tags=["combat"])

@router.post("/combat/{session_id}/class-feature", response_model=CombatActionResult)
async def use_class_feature(
    session_id: str,
    req: ClassFeatureRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    使用职业战斗特性：
    - second_wind:  Fighter 1+, 恢复 1d10+level HP, 附赠行动, 每短休1次
    - action_surge: Fighter 2+, 本回合获得额外行动, 每短休1次
    - rage:         Barbarian 1+, 进入/退出狂暴, 附赠行动
    - cunning_action_dash: Rogue 2+, 附赠行动冲刺
    - cunning_action_disengage: Rogue 2+, 附赠行动脱离
    - cunning_action_hide: Rogue 2+, 附赠行动隐匿
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    player = await db.get(Character, session.player_character_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player_id = session.player_character_id
    ts = _get_ts(combat, player_id)
    p_class = _normalize_class(player.char_class)
    p_level = player.level
    derived = player.derived or {}
    class_res = dict(player.class_resources or {})

    feature = req.feature_name
    narration = ""
    dice_roll = None  # {faces, result, label} for frontend dice animation

    # ── Second Wind (Fighter) ─────────────────────────────
    if feature == "second_wind":
        if p_class != "Fighter":
            raise HTTPException(400, "只有战士可以使用活力恢复")
        if class_res.get("second_wind_used", False):
            raise HTTPException(400, "本次休息后已使用过活力恢复")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        heal_roll = roll_dice(f"1d10+{p_level}")
        heal_amt  = heal_roll["total"]
        hp_max    = derived.get("hp_max", player.hp_current)
        old_hp    = player.hp_current
        player.hp_current = min(hp_max, player.hp_current + heal_amt)

        class_res["second_wind_used"] = True
        player.class_resources = class_res
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)

        narration = f"🛡️ {player.name} 使用「活力恢复」！1d10+{p_level}={heal_amt}，恢复 {player.hp_current - old_hp} HP（{player.hp_current}/{hp_max}）"
        dice_roll = {"faces": 10, "result": heal_amt, "label": f"活力恢复 1d10+{p_level}"}

    # ── Action Surge (Fighter) ────────────────────────────
    elif feature == "action_surge":
        if p_class != "Fighter":
            raise HTTPException(400, "只有战士可以使用行动奔涌")
        if p_level < 2:
            raise HTTPException(400, "需要战士2级以上才能使用行动奔涌")
        if class_res.get("action_surge_used", False):
            raise HTTPException(400, "本次休息后已使用过行动奔涌")

        class_res["action_surge_used"] = True
        player.class_resources = class_res
        # 重置行动配额（不重置移动力和附赠行动）
        ts["action_used"]  = False
        ts["attacks_made"]  = 0
        _save_ts(combat, player_id, ts)

        narration = f"⚡ {player.name} 使用「行动奔涌」！本回合获得额外一次完整行动！"

    # ── Rage (Barbarian) ──────────────────────────────────
    elif feature == "rage":
        if p_class != "Barbarian":
            raise HTTPException(400, "只有野蛮人可以使用狂暴")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        is_raging = class_res.get("raging", False)
        if is_raging:
            # 退出狂暴
            class_res["raging"] = False
            player.class_resources = class_res
            # 移除 rage 给的伤害抗性条件
            conditions = list(player.conditions or [])
            player.conditions = [c for c in conditions if c != "raging"]
            narration = f"😤 {player.name} 停止了狂暴。"
        else:
            # 进入狂暴
            rage_remaining = class_res.get("rage_remaining", svc.get_rage_uses(p_level))
            if rage_remaining <= 0:
                raise HTTPException(400, "狂暴次数已用尽（长休后恢复）")
            class_res["raging"] = True
            class_res["rage_remaining"] = rage_remaining - 1
            player.class_resources = class_res
            ts["bonus_action_used"] = True
            _save_ts(combat, player_id, ts)
            rage_bonus = svc.get_rage_bonus(p_level)
            narration = f"🔥 {player.name} 进入狂暴！近战伤害+{rage_bonus}，物理伤害抗性！（剩余{rage_remaining - 1}次）"

    # ── Cunning Action — Dash (Rogue) ─────────────────────
    elif feature == "cunning_action_dash":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        ts["movement_max"]      = ts["movement_max"] * 2
        _save_ts(combat, player_id, ts)
        narration = f"💨 {player.name} 使用「灵巧动作-冲刺」！移动力翻倍！"

    # ── Cunning Action — Disengage (Rogue) ────────────────
    elif feature == "cunning_action_disengage":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        ts["disengaged"]        = True
        _save_ts(combat, player_id, ts)
        narration = f"💨 {player.name} 使用「灵巧动作-脱离」！本回合移动不触发借机攻击。"

    # ── Cunning Action — Hide (Rogue) ─────────────────────
    elif feature == "cunning_action_hide":
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧动作")
        if p_level < 2:
            raise HTTPException(400, "需要游荡者2级以上才能使用灵巧动作")
        if ts["bonus_action_used"]:
            raise HTTPException(400, "本回合附赠行动已用尽")

        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        # 添加隐匿条件（攻击时获得优势）
        conditions = list(player.conditions or [])
        if "hidden" not in conditions:
            conditions.append("hidden")
            player.conditions = conditions
        narration = f"🫥 {player.name} 使用「灵巧动作-隐匿」！下次攻击获得优势！"

    # ── Fighting Spirit (Samurai Fighter) ────────────────
    elif feature == "fighting_spirit":
        if not (p_class == "Fighter"):
            raise HTTPException(400, "非战士无法使用战意")
        fs_rem = class_res.get("fighting_spirit_remaining", 0)
        if fs_rem <= 0:
            raise HTTPException(400, "战意次数已用完")
        class_res["fighting_spirit_remaining"] = fs_rem - 1
        # Grant advantage on all attacks this turn + temp HP = fighter level
        ts["fighting_spirit_active"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚔️ {player.name} 集中精神，燃起不屈的战意！本回合所有攻击获得优势，获得 {player.level} 点临时生命值。"

    # ── Bardic Inspiration (Bard) ─────────────────────────
    elif feature == "bardic_inspiration":
        if not (p_class == "Bard"):
            raise HTTPException(400, "非吟游诗人无法使用灵感骰")
        bi_rem = class_res.get("bardic_inspiration_remaining", 0)
        if bi_rem <= 0:
            raise HTTPException(400, "灵感骰次数已用完")
        class_res["bardic_inspiration_remaining"] = bi_rem - 1
        derived = player.derived or {}
        die = derived.get("subclass_effects", {}).get("inspiration_die", "d6")
        bi_faces = int(die.replace("d", "")) if die.startswith("d") else 6
        bi_roll = roll_dice(die)
        player.class_resources = class_res
        narration = f"🎵 {player.name} 演奏了一段鼓舞人心的旋律！一名盟友获得 {die} 灵感骰（{bi_roll['rolls'][0]}）。"
        dice_roll = {"faces": bi_faces, "result": bi_roll["rolls"][0], "label": f"灵感骰 {die}"}

    # ── Ki: Flurry of Blows (Monk, 1 ki) ─────────────────
    elif feature == "ki_flurry":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用疾风连击")
        ki = class_res.get("ki_remaining", 0)
        if ki < 1:
            raise HTTPException(400, "气不足")
        class_res["ki_remaining"] = ki - 1
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        # Roll 2 unarmed attacks
        d = player.derived or {}
        atk_mod = d.get("attack_bonus", 2)
        martial_die = "1d4" if player.level < 5 else ("1d6" if player.level < 11 else ("1d8" if player.level < 17 else "1d10"))
        results = []
        for i in range(2):
            atk = roll_dice("1d20")
            hit_total = atk["rolls"][0] + atk_mod
            results.append(f"攻击{i+1}: d20={atk['rolls'][0]}+{atk_mod}={hit_total}")
        player.class_resources = class_res
        narration = f"👊 {player.name} 以气驱动疾风连击！{' | '.join(results)}"
        dice_roll = {"faces": 20, "result": roll_dice("1d20")["rolls"][0], "label": "疾风连击"}

    # ── Ki: Stunning Strike (Monk, 1 ki) ──────────────────
    elif feature == "ki_stunning_strike":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用震慑打击")
        ki = class_res.get("ki_remaining", 0)
        if ki < 1:
            raise HTTPException(400, "气不足")
        class_res["ki_remaining"] = ki - 1
        player.class_resources = class_res
        ki_dc = 8 + derived.get("proficiency_bonus", 2) + derived.get("ability_modifiers", {}).get("wis", 0)
        narration = f"💥 {player.name} 将气灌注于一击之中！目标必须进行 DC{ki_dc} 体质豁免，失败则被震慑至你的下一回合结束。"
        dice_roll = {"faces": 20, "result": ki_dc, "label": f"震慑打击 DC{ki_dc}"}

    # ── Shadow Step (Shadow Monk, 2 ki) ───────────────────
    elif feature == "shadow_step":
        if not (p_class == "Monk"):
            raise HTTPException(400, "非武僧无法使用暗影步")
        ki = class_res.get("ki_remaining", 0)
        if ki < 2:
            raise HTTPException(400, "气不足（需要2点）")
        class_res["ki_remaining"] = ki - 2
        player.class_resources = class_res
        narration = f"🌑 {player.name} 融入阴影之中，瞬间出现在另一片黑暗处！下一次近战攻击获得优势。"
        dice_roll = {"faces": 20, "result": roll_dice("1d20")["rolls"][0], "label": "暗影步"}

    # ── Channel Divinity (Paladin) ────────────────────────
    elif feature == "channel_divinity":
        if not (p_class == "Paladin"):
            raise HTTPException(400, "非圣武士无法引导神力")
        if class_res.get("channel_divinity_used"):
            raise HTTPException(400, "引导神力已使用（每次短休恢复）")
        class_res["channel_divinity_used"] = True
        sub_effects = (player.derived or {}).get("subclass_effects", {})
        if sub_effects.get("devotion"):
            narration = f"✨ {player.name} 引导神力——神圣武器！武器散发圣光，攻击加上魅力修正，持续1分钟。"
        elif sub_effects.get("vengeance"):
            narration = f"⚔️ {player.name} 引导神力——仇敌誓约！标记一个目标，对其攻击获得优势，持续1分钟。"
            ts["vow_of_enmity_active"] = True
            _save_ts(combat, player_id, ts)
        elif sub_effects.get("ancients"):
            narration = f"🌿 {player.name} 引导神力——自然之怒！藤蔓缠绕目标使其束缚！"
        elif sub_effects.get("glory"):
            narration = f"🌟 {player.name} 引导神力——鼓舞冲锋！30尺内盟友移动速度+10尺，持续10分钟。"
        else:
            narration = f"✨ {player.name} 引导神力！"
        player.class_resources = class_res

    # ── Lay on Hands (Paladin) ────────────────────────────
    elif feature == "lay_on_hands":
        if not (p_class == "Paladin"):
            raise HTTPException(400, "非圣武士无法使用圣手")
        pool = class_res.get("lay_on_hands_remaining", 0)
        if pool <= 0:
            raise HTTPException(400, "圣手治疗池已耗尽")
        # Heal 5 HP (or remaining pool, whichever is less)
        heal_amount = min(5, pool)
        class_res["lay_on_hands_remaining"] = pool - heal_amount
        hp_max = (player.derived or {}).get("hp_max", player.hp_current)
        player.hp_current = min(hp_max, player.hp_current + heal_amount)
        player.class_resources = class_res
        narration = f"🤲 {player.name} 将圣光注入伤口，恢复了 {heal_amount} 点生命值！（剩余治疗池: {pool - heal_amount}）"
        dice_roll = {"faces": 20, "result": heal_amount, "label": f"圣手治疗 +{heal_amount}HP"}

    # ── War Priest Attack (War Cleric) ────────────────────
    elif feature == "war_priest_attack":
        if not (p_class == "Cleric"):
            raise HTTPException(400, "非牧师无法使用战争牧师")
        wp_rem = class_res.get("war_priest_remaining", 0)
        if wp_rem <= 0:
            raise HTTPException(400, "战争牧师额外攻击次数已用完")
        class_res["war_priest_remaining"] = wp_rem - 1
        ts["bonus_action_used"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚔️ {player.name} 以战神之名发动额外攻击！本回合可用附赠动作进行一次武器攻击。"

    # ── Destructive Wrath (Tempest Cleric) ────────────────
    elif feature == "destructive_wrath":
        if not (p_class == "Cleric"):
            raise HTTPException(400, "非牧师无法使用毁灭之怒")
        if class_res.get("channel_divinity_used"):
            raise HTTPException(400, "引导神力已使用")
        class_res["channel_divinity_used"] = True
        ts["destructive_wrath_active"] = True
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"⚡ {player.name} 引导神力——毁灭之怒！下一次闪电或雷鸣伤害将自动取最大值！"

    # ── Wild Shape (Moon Druid) ───────────────────────────
    elif feature == "wild_shape":
        if not (p_class == "Druid"):
            raise HTTPException(400, "非德鲁伊无法使用野性形态")
        ws_rem = class_res.get("wild_shape_remaining", 0)
        if ws_rem <= 0:
            raise HTTPException(400, "野性形态次数已用完")
        class_res["wild_shape_remaining"] = ws_rem - 1
        sub_effects = (player.derived or {}).get("subclass_effects", {})
        max_cr = sub_effects.get("wild_shape_max_cr", 0.25)
        # Default to Bear form
        from services.dnd_rules import WILD_SHAPE_FORMS
        form_name = "Bear" if max_cr >= 1 else "Wolf"
        form = WILD_SHAPE_FORMS.get(form_name, {})
        class_res["wild_shape_active"] = form_name
        class_res["wild_shape_hp"] = form.get("hp", 20)
        player.class_resources = class_res
        narration = f"🐻 {player.name} 的身体扭曲变化，化身为{form_name}！获得 {form.get('hp',20)} 点额外生命值，AC {form.get('ac',12)}。"
        dice_roll = {"faces": 20, "result": form.get("hp", 20), "label": f"野性形态·{form_name}"}

    # ── Symbiotic Entity (Spores Druid) ───────────────────
    elif feature == "symbiotic_entity":
        if not (p_class == "Druid"):
            raise HTTPException(400, "非德鲁伊无法激活共生实体")
        ws_rem = class_res.get("wild_shape_remaining", 0)
        if ws_rem <= 0:
            raise HTTPException(400, "需要消耗一次野性形态")
        class_res["wild_shape_remaining"] = ws_rem - 1
        temp_hp = (player.derived or {}).get("subclass_effects", {}).get("symbiotic_temp_hp", 4 * player.level)
        class_res["symbiotic_entity_active"] = True
        player.class_resources = class_res
        narration = f"🍄 {player.name} 激活共生实体！孢子覆盖全身，获得 {temp_hp} 点临时生命值，近战附加毒素伤害。"
        dice_roll = {"faces": 20, "result": temp_hp, "label": f"共生实体 +{temp_hp}临时HP"}

    # ── Tides of Chaos (Wild Magic Sorcerer) ──────────────
    elif feature == "tides_of_chaos":
        if not (p_class == "Sorcerer"):
            raise HTTPException(400, "非术士无法使用混沌之潮")
        if class_res.get("tides_of_chaos_used"):
            raise HTTPException(400, "混沌之潮已使用（每次长休恢复）")
        class_res["tides_of_chaos_used"] = True
        ts["tides_of_chaos_active"] = True  # Next d20 roll gets advantage
        _save_ts(combat, player_id, ts)
        player.class_resources = class_res
        narration = f"🌀 {player.name} 引导体内不稳定的魔法能量！下一次攻击/检定/豁免获得优势。但这可能触发野蛮魔法涌动..."

    # ── Portent (Divination Wizard) ───────────────────────
    elif feature == "portent":
        if not (p_class == "Wizard"):
            raise HTTPException(400, "非法师无法使用预言骰")
        p_rem = class_res.get("portent_remaining", 0)
        if p_rem <= 0:
            raise HTTPException(400, "预言骰已用完（每次长休恢复）")
        class_res["portent_remaining"] = p_rem - 1
        portent_roll = roll_dice("1d20")
        class_res["portent_value"] = portent_roll["rolls"][0]
        player.class_resources = class_res
        narration = f"🔮 {player.name} 预见了命运的走向——预言骰: {portent_roll['rolls'][0]}！可以用此值替换任意一次d20检定。"
        dice_roll = {"faces": 20, "result": portent_roll["rolls"][0], "label": "预言骰"}

    else:
        raise HTTPException(400, f"未知职业特性：{feature}")

    # LLM vivid narration for class features
    vivid = await narrate_action(
        actor_name=player.name, actor_class=p_class,
        target_name="",
        action_type="class_feature",
        extra_details=narration,
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {"type": "class_feature", "feature": feature},
    ))
    await db.commit()

    return {
        "action":          "class_feature",
        "feature":         feature,
        "narration":       narration,
        "turn_state":      ts,
        "class_resources": class_res,
        "hp_current":      player.hp_current,
        "hp_max":          derived.get("hp_max", player.hp_current),
        "dice_roll":       dice_roll,
    }
