"""Full E2E combat test for P0 features"""
import sys, asyncio, json, uuid
sys.path.insert(0, '.')

import httpx

async def full_e2e():
    async with httpx.AsyncClient(base_url='http://localhost:8002', timeout=300) as c:
        mods = (await c.get('/modules/')).json()
        if not mods:
            print('No modules! Upload one first.')
            return
        module_id = mods[0]['id']
        print(f'Module: {mods[0]["name"]}')

        # 1. Create Paladin Lv5
        print('\n=== 1. Create Paladin Lv5 ===')
        char = (await c.post('/characters/create', json={
            'module_id': module_id, 'name': '亚瑟', 'race': '人类',
            'char_class': '圣武士', 'subclass': 'Devotion', 'level': 5,
            'background': '士兵',
            'ability_scores': {'str':16,'dex':10,'con':14,'int':8,'wis':12,'cha':14},
            'proficient_skills': [],
            'fighting_style': 'Dueling',
            'equipment_choice': 0, 'bonus_languages': [], 'feats': [],
        })).json()
        if 'id' not in char:
            print(f'FAIL: {json.dumps(char, ensure_ascii=False)[:200]}')
            return
        char_id = char['id']
        der = char.get('derived', {})
        print(f'  HP={char["hp_current"]} AC={der.get("ac")} ATK={der.get("attack_bonus")}')
        print(f'  melee_damage_bonus={der.get("melee_damage_bonus")} (Dueling +2)')
        print(f'  Spell slots: {char.get("spell_slots")}')

        # 2. Create session (no companions for simpler test)
        print('\n=== 2. Create Session ===')
        sess = (await c.post('/game/sessions', json={
            'module_id': module_id, 'player_character_id': char_id, 'companion_ids': [],
        })).json()
        session_id = sess.get('session_id', sess.get('id', ''))
        print(f'  Session: {session_id[:12]}...')

        # 3. Init combat directly
        print('\n=== 3. Init Combat ===')
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Session as Sess, CombatState, Character
        from services.dnd_rules import roll_initiative

        async with AsyncSessionLocal() as db:
            session_obj = (await db.execute(select(Sess).where(Sess.id == session_id))).scalar_one()
            chars = (await db.execute(select(Character).where(Character.session_id == session_id))).scalars().all()

            enemies = [{
                'id': f'enemy_{uuid.uuid4().hex[:8]}', 'name': '哥布林',
                'hp': 12, 'hp_current': 12, 'hp_max': 12, 'ac': 13,
                'attack_bonus': 4, 'damage_dice': '1d6+2', 'damage_type': 'slashing',
                'conditions': [], 'dead': False, 'is_player': False, 'is_enemy': True,
                'resistances': [], 'immunities': [], 'vulnerabilities': [],
                'derived': {'hp_max':12,'ac':13,'attack_bonus':4,
                    'ability_modifiers':{'str':1,'dex':2,'con':1,'int':-1,'wis':0,'cha':-1}},
                'actions': [{'name':'弯刀','type':'melee_attack','attack_bonus':4,
                    'damage_dice':'1d6+2','damage_type':'slashing'}],
            }]

            combatants = [
                {'id': str(ch.id), 'name': ch.name,
                 'initiative': (ch.derived or {}).get('initiative', 0),
                 'is_player': ch.is_player, 'is_enemy': False}
                for ch in chars
            ] + enemies
            turn_order = roll_initiative(combatants)

            # Force player first
            for i, t in enumerate(turn_order):
                if t.get('is_player'):
                    turn_order.insert(0, turn_order.pop(i))
                    break

            positions = {str(chars[0].id): {'x': 4, 'y': 5}}
            positions[enemies[0]['id']] = {'x': 5, 'y': 5}  # Adjacent

            gs = dict(session_obj.game_state or {})
            gs['enemies'] = enemies
            session_obj.game_state = gs
            session_obj.combat_active = True

            combat = CombatState(
                id=str(uuid.uuid4()), session_id=session_id,
                turn_order=turn_order, current_turn_index=0,
                round_number=1, entity_positions=positions,
                grid_data={}, combat_log=[], turn_states={},
            )
            db.add(combat)
            await db.commit()

        enemy_id = enemies[0]['id']
        print(f'  Player at (4,5), Enemy at (5,5) — adjacent')
        print(f'  Turn order: {" → ".join(t["name"] for t in turn_order)}')

        # 4. Player attack
        print('\n=== 4. Player Attack (should have Extra Attack) ===')
        atk1 = (await c.post(f'/game/combat/{session_id}/action', json={
            'entity_id': char_id, 'target_id': enemy_id, 'action_type': 'melee',
        })).json()

        if 'detail' in atk1:
            print(f'  ERROR: {atk1["detail"]}')
            return

        print(f'  Attack 1: {atk1.get("narration", "")[:80]}')
        print(f'  attacks_made={atk1.get("attacks_made")}/{atk1.get("attacks_max")}')
        hit1 = atk1.get('attack_result', {}).get('hit', False)

        if hit1:
            print(f'  HIT! Damage={atk1.get("damage")}')

            # Test Divine Smite
            print('\n=== 5. Divine Smite ===')
            smite = (await c.post(f'/game/combat/{session_id}/smite', json={
                'slot_level': 1,
            })).json()
            if 'detail' in smite:
                print(f'  Smite ERROR: {smite["detail"]}')
            else:
                print(f'  Smite damage: {smite.get("smite_damage")} ({smite.get("smite_dice")})')
                print(f'  Target HP: {smite.get("target_new_hp")}')
        else:
            print(f'  MISS — skipping smite test')

        # Extra Attack (2nd attack)
        am = atk1.get('attacks_made', 1)
        mx = atk1.get('attacks_max', 1)
        if am < mx:
            print(f'\n=== 6. Extra Attack ({am+1}/{mx}) ===')
            atk2 = (await c.post(f'/game/combat/{session_id}/action', json={
                'entity_id': char_id, 'target_id': enemy_id, 'action_type': 'melee',
            })).json()
            if 'detail' in atk2:
                print(f'  ERROR: {atk2["detail"]}')
            else:
                print(f'  Attack 2: {atk2.get("narration", "")[:80]}')
        else:
            print(f'\n  No Extra Attack available (attacks_max={mx})')

        # End turn
        print('\n=== 7. End Turn + AI Turns ===')
        end = (await c.post(f'/game/combat/{session_id}/end-turn')).json()
        if 'detail' in end:
            print(f'  End turn ERROR: {end["detail"]}')
        else:
            print(f'  Next index: {end.get("next_turn_index")}, Round: {end.get("round_number")}')

        # AI turns
        for i in range(5):
            cs = (await c.get(f'/game/combat/{session_id}')).json()
            ct = cs['turn_order'][cs['current_turn_index']]
            if ct.get('is_player'):
                print(f'  Back to player! Round {cs["round_number"]}')
                break
            try:
                ai = (await c.post(f'/game/combat/{session_id}/ai-turn')).json()
                if 'detail' in ai:
                    print(f'  AI error: {ai["detail"]}')
                    break
                print(f'  AI: {ai.get("actor_name")} — {ai.get("narration","")[:60]}')
            except Exception as e:
                print(f'  AI exception: {e}')
                break

        # 8. Test short rest
        print('\n=== 8. Short Rest (Hit Dice) ===')
        # End combat first
        await c.post(f'/game/combat/{session_id}/end')
        rest = (await c.post(f'/game/sessions/{session_id}/rest?rest_type=short')).json()
        print(f'  Rest result: {json.dumps(rest, ensure_ascii=False)[:200]}')

        print('\n=== ALL TESTS COMPLETE ===')

asyncio.run(full_e2e())
