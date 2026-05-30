"""
冒烟测试：所有关键模块能导入，所有路由都被 FastAPI 注册。

这一层跑得最快（< 1s），每次提交都应该通过。如果它挂了通常是
import 层面的错误（拼写 / 循环 import / 缺依赖），直接定位就好。
"""


def test_import_backend_main():
    """main.py 能完整 import。"""
    import main
    assert main.app.title == "AI TRPG Backend"


def test_import_all_api_modules():
    """所有 api/* 子模块能 import。"""
    from api import auth, game, modules, characters, character_inventory, rooms, ws, deps
    from api.game_routes import actions, campaign, checks, sessions
    from api import combat
    assert all([auth.router, game.router, modules.router, characters.router,
                character_inventory.router, rooms.router, ws.router, combat.router,
                actions.router, campaign.router, checks.router, sessions.router])


def test_import_combat_subpackage():
    """拆分后的 api/combat/ 所有子模块能独立 import。"""
    from api.combat import (
        _shared, schemas,
        info, turns, movement, attacks, attack_rolls, reactions,
        spell_catalog, spell_rolls, spellcasting, conditions, deathsaves, ai_turn, ai_end,
        ai_turn_actions, ai_turn_spell, ai_turn_attack,
        grapples, smites, class_features, maneuvers,
    )
    # 每个子模块应该都有自己的 router 实例
    for mod in (info, turns, movement, attacks, attack_rolls, reactions,
                spell_catalog, spell_rolls, spellcasting, conditions, deathsaves, ai_turn, ai_end,
                grapples, smites, class_features, maneuvers):
        assert hasattr(mod, "router"), f"{mod.__name__} 缺少 router"


def test_combat_package_exports_legacy_helpers():
    """game.py 的自然语言战斗分支仍依赖这些包级 helper 导出。"""
    from api.combat import (
        _get_ts, _save_ts, _check_attack_range, _ai_move_toward,
        _chebyshev_dist, _calc_entity_turn_limits,
    )
    assert all([
        _get_ts, _save_ts, _check_attack_range, _ai_move_toward,
        _chebyshev_dist, _calc_entity_turn_limits,
    ])


def test_import_all_services():
    """所有 services/* 能 import（含 P1 新增的 character_roster）。"""
    from services import (
        dnd_rules, combat_service, spell_service,
        context_builder, state_applicator,
        character_roster, langgraph_client,
        rag_service, local_rag_service,
    )
    assert character_roster.CharacterRoster is not None


def test_import_split_dnd_rule_modules():
    """dnd_rules.py 应保持兼容门面，实际规则分层放在独立模块里。"""
    from services import (
        dnd_character_rules,
        dnd_data,
        dnd_derived,
        dnd_dice,
        dnd_items,
        dnd_subclass_effects,
        dnd_wild_magic,
    )

    assert all([
        dnd_character_rules,
        dnd_data,
        dnd_derived,
        dnd_dice,
        dnd_items,
        dnd_subclass_effects.apply_subclass_effects,
        dnd_wild_magic,
    ])


def test_import_split_combat_service_modules():
    """combat_service.py 保持兼容门面，纯规则按职责拆到独立模块。"""
    from services import (
        combat_attack_service,
        combat_condition_service,
        combat_damage_service,
        encounter_balance_service,
        exploration_rules_service,
        combat_feature_rules,
        combat_legendary_action_service,
        combat_tactical_service,
    )
    from services.combat_service import AttackResult, CombatService

    assert combat_attack_service.AttackResult is AttackResult
    assert combat_attack_service.resolve_melee_attack is not None
    assert combat_damage_service.apply_damage is not None
    assert encounter_balance_service.estimate_encounter_difficulty is not None
    assert exploration_rules_service.passive_perception is not None
    assert combat_condition_service.check_concentration is not None
    assert combat_feature_rules.calc_divine_smite_damage is not None
    assert combat_legendary_action_service.initialize_legendary_actions is not None
    assert combat_tactical_service.choose_ai_target is not None
    assert CombatService.resolve_melee_attack is not None


def test_import_split_room_group_service():
    """room_service.py 对外兼容，分队状态逻辑放在独立服务里。"""
    from services import (
        room_ai_companion_service,
        room_group_service,
        room_group_state_utils,
        room_info_service,
        room_lifecycle_service,
        room_member_service,
        room_start_service,
    )

    assert room_group_service.DEFAULT_GROUP_ID == "main"
    assert room_group_state_utils.normalize_party_groups is not None
    assert room_lifecycle_service.create_room is not None
    assert room_member_service.list_members is not None
    assert room_ai_companion_service.fill_with_ai_companions is not None
    assert room_start_service.start_game is not None
    assert room_info_service.get_room_info is not None


def test_import_split_game_combat_action_modules():
    """自然语言战斗入口保持兼容，动作执行与上下文组装放进独立模块。"""
    from services import (
        game_combat_action_context,
        game_combat_action_executor,
        game_combat_action_steps,
        game_combat_creative_service,
    )
    from services.game_combat_action_service import _execute_attack_action, _choose_narration_action_type

    assert game_combat_action_context.build_combat_parser_state is not None
    assert game_combat_action_executor.execute_parsed_combat_actions is not None
    assert game_combat_action_steps.execute_attack_action is not None
    assert game_combat_creative_service.execute_creative_action is not None
    assert _execute_attack_action is not None
    assert _choose_narration_action_type is not None


def test_import_split_game_action_route_helpers():
    """game_routes/actions.py 保持路由入口，多人/运行时辅助逻辑拆到独立模块。"""
    from api.game_routes import action_multiplayer, action_runtime
    from api.game_routes.actions import (
        _broadcast_dm_thinking,
        _handle_multiplayer_table_only_result,
        _load_latest_combat_state,
    )

    assert action_multiplayer.handle_multiplayer_table_only_result is _handle_multiplayer_table_only_result
    assert action_runtime.broadcast_dm_thinking is _broadcast_dm_thinking
    assert action_runtime.load_latest_combat_state is _load_latest_combat_state


def test_import_split_character_inventory_route_modules():
    """character_inventory.py 保持路由入口，装备/交易/使用物品拆到独立模块。"""
    from api import (
        character_inventory_equipment,
        character_inventory_shop,
        character_inventory_use_item,
    )
    from api.character_inventory import (
        _buy_character_item,
        _recalculate_character_derived,
        _use_character_item,
    )

    assert character_inventory_equipment.recalculate_character_derived is _recalculate_character_derived
    assert character_inventory_shop.buy_character_item is _buy_character_item
    assert character_inventory_use_item.use_character_item is _use_character_item


def test_import_split_character_route_modules():
    """characters.py 保持路由入口，创角/队友/成长维护拆到独立模块。"""
    from api import character_create, character_party, character_progression
    from api.characters import (
        _create_player_character,
        _generate_ai_party,
        _level_up_character,
    )

    assert character_create.create_player_character is _create_player_character
    assert character_party.generate_ai_party is _generate_ai_party
    assert character_progression.level_up_character is _level_up_character


def test_import_split_ai_combat_agent_modules():
    """ai_combat_agent.py 保持旧入口，prompt / 上下文 / 解析工具拆成独立模块。"""
    from services import (
        ai_combat_agent_context,
        ai_combat_agent_parser,
        ai_combat_agent_prompts,
    )
    from services.ai_combat_agent import ENEMY_DECISION_PROMPT, _format_entity, calc_difficulty

    assert ai_combat_agent_prompts.ENEMY_DECISION_PROMPT is ENEMY_DECISION_PROMPT
    assert ai_combat_agent_context.format_entity is not None
    assert ai_combat_agent_parser.parse_ai_decision_response is not None
    assert _format_entity is not None
    assert calc_difficulty({"level_min": 1}) == "easy"


def test_import_split_combat_ai_spell_modules():
    """AI 施法服务保持旧入口，效果解析拆到独立模块。"""
    from services import (
        combat_ai_spell_damage_service,
        combat_ai_spell_effect_service,
        combat_ai_spell_models,
    )
    from services.combat_ai_spell_service import AiSpellResolution, _apply_ai_damage_spell

    assert combat_ai_spell_models.AiSpellResolution is AiSpellResolution
    assert combat_ai_spell_damage_service.apply_ai_damage_spell is not None
    assert combat_ai_spell_effect_service.apply_ai_heal_spell is not None
    assert _apply_ai_damage_spell is not None


def test_import_split_state_applicator_modules():
    """StateApplicator 保持入口，返回模型和日志写入拆成独立模块。"""
    from services import state_apply_result, state_log_service
    from services.state_applicator import ApplyResult

    assert state_apply_result.ApplyResult is ApplyResult
    assert state_log_service.append_session_history is not None
    assert state_log_service.write_game_logs is not None


def test_import_split_context_builder_modules():
    """ContextBuilder 保持旧入口，状态快照/多人上下文/记忆来源拆到独立模块。"""
    from services import (
        context_builder_memory,
        context_builder_multiplayer,
        context_builder_snapshots,
    )
    from services.context_builder import _build_game_state_payload

    assert context_builder_snapshots.build_game_state_payload is _build_game_state_payload
    assert context_builder_multiplayer.build_multiplayer_context is not None
    assert context_builder_memory.build_campaign_memory is not None


def test_import_split_inventory_modules():
    """inventory_service.py 保持旧入口，背包交易/装备/物品使用拆成独立模块。"""
    from services import (
        inventory_equipment_service,
        inventory_item_service,
        inventory_models,
        inventory_trade_service,
    )
    from services.inventory_service import InventoryError, buy_item, update_equipment

    assert inventory_models.InventoryError is InventoryError
    assert inventory_item_service.prepare_gear_item_use is not None
    assert inventory_trade_service.buy_item is buy_item
    assert inventory_equipment_service.update_equipment is update_equipment


def test_import_split_action_parser_modules():
    """action_parser.py 保持 parse_combat_action 入口，prompt/local/LLM/fallback 拆分。"""
    from services import action_parser_fallbacks, action_parser_llm, action_parser_local, action_parser_prompts
    from services.action_parser import PARSE_PROMPT, _parse_with_llm

    assert action_parser_prompts.PARSE_PROMPT is PARSE_PROMPT
    assert action_parser_local.parse_local_combat_action is not None
    assert action_parser_llm.parse_with_llm is _parse_with_llm
    assert action_parser_fallbacks.fallback_combat_action is not None


def test_import_split_multiplayer_dm_agent_modules():
    """多人 DM Agent 保持入口，文本/可见性工具拆为独立模块。"""
    from services.graphs import multiplayer_dm_agent_formatters
    from services.graphs.multiplayer_dm_agent import _build_effective_action_text

    assert multiplayer_dm_agent_formatters.build_effective_action_text is _build_effective_action_text
    assert multiplayer_dm_agent_formatters.resolve_visible_users is not None


def test_combat_routes_registered():
    """combat 子包对外应暴露 24 个路由（拆分不能漏路由）。"""
    from api.combat import router
    assert len(router.routes) == 24, f"期望 24 个 combat 路由，实际 {len(router.routes)}"


def test_all_app_routes_have_path():
    """主 app 注册的所有 route 都应有 path 和 methods。"""
    import main
    named = [r for r in main.app.routes if hasattr(r, "path")]
    # 粗略下界：至少 50 个路由（当前约 71）
    assert len(named) >= 50, f"路由数量异常：{len(named)}"


def test_combat_route_paths_unchanged():
    """拆分前后 /game/combat/* 的路径必须完全不变，客户端才不会感知到。"""
    from api.combat import router

    expected = {
        "/game/combat/{session_id}",
        "/game/combat/{session_id}/action",
        "/game/combat/{session_id}/ai-turn",
        "/game/combat/{session_id}/attack-roll",
        "/game/combat/{session_id}/class-feature",
        "/game/combat/{session_id}/condition/add",
        "/game/combat/{session_id}/condition/remove",
        "/game/combat/{session_id}/damage-roll",
        "/game/combat/{session_id}/death-save",
        "/game/combat/{session_id}/end",
        "/game/combat/{session_id}/end-turn",
        "/game/combat/{session_id}/grapple-shove",
        "/game/combat/{session_id}/inspect",
        "/game/combat/{session_id}/maneuver",
        "/game/combat/{session_id}/move",
        "/game/combat/{session_id}/predict",
        "/game/combat/{session_id}/reaction",
        "/game/combat/{session_id}/skill-bar",
        "/game/combat/{session_id}/smite",
        "/game/combat/{session_id}/spell",
        "/game/combat/{session_id}/spell-confirm",
        "/game/combat/{session_id}/spell-roll",
        "/game/spells",
        "/game/spells/class/{class_name}",
    }
    actual = {r.path for r in router.routes if hasattr(r, "path")}
    assert actual == expected, f"路由集合变化：缺失={expected-actual}，多余={actual-expected}"


def test_game_route_paths_unchanged():
    """拆分 game.py 时 /game 非 combat 路由不能变。"""
    from api.game import router

    expected = {
        "/game/action",
        "/game/sessions",
        "/game/sessions/{session_id}",
        "/game/sessions/{session_id}/ai-takeover",
        "/game/sessions/{session_id}/checkpoint",
        "/game/sessions/{session_id}/encounter-template/select",
        "/game/sessions/{session_id}/journal",
        "/game/sessions/{session_id}/loot",
        "/game/sessions/{session_id}/loot/claim",
        "/game/sessions/{session_id}/rest",
        "/game/skill-check",
    }
    actual = {r.path for r in router.routes if hasattr(r, "path")}
    assert actual == expected, f"game 路由集合变化：缺失={expected-actual}，多余={actual-expected}"
