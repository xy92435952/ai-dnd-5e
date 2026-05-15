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


def test_combat_routes_registered():
    """combat 子包对外应暴露 23 个路由（拆分不能漏路由）。"""
    from api.combat import router
    assert len(router.routes) == 23, f"期望 23 个 combat 路由，实际 {len(router.routes)}"


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
        "/game/sessions/{session_id}/journal",
        "/game/sessions/{session_id}/rest",
        "/game/skill-check",
    }
    actual = {r.path for r in router.routes if hasattr(r, "path")}
    assert actual == expected, f"game 路由集合变化：缺失={expected-actual}，多余={actual-expected}"
