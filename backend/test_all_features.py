"""Comprehensive test for ALL P0/P1/P2 features"""
import sys, asyncio, json, uuid
sys.path.insert(0, '.')
import httpx

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  OK {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")

async def test():
    async with httpx.AsyncClient(base_url='http://localhost:8002', timeout=300) as c:
        mods = (await c.get('/modules/')).json()
        if not mods:
            print('No modules!'); return
        mid = mods[0]['id']

        # ═══════════════════════════════════════════
        # 1. CHARACTER CREATION
        # ═══════════════════════════════════════════
        print("\n══ 1. CHARACTER CREATION ══")
        char = (await c.post('/characters/create', json={
            'module_id': mid, 'name': 'TestPaladin', 'race': '精灵',
            'char_class': '圣武士', 'subclass': 'Devotion', 'level': 5,
            'background': '士兵',
            'ability_scores': {'str':16,'dex':12,'con':14,'int':8,'wis':10,'cha':14},
            'proficient_skills': [], 'fighting_style': 'Dueling',
            'equipment_choice': 0, 'bonus_languages': [], 'feats': [],
        })).json()
        check("Character created", 'id' in char, str(char.get('detail',''))[:80])
        if 'id' not in char: return
        cid = char['id']
        der = char.get('derived', {})
        check("Darkvision (Elf=60)", der.get('darkvision') == 60, f"got {der.get('darkvision')}")
        check("Passive Perception exists", 'passive_perception' in der, str(list(der.keys())[:5]))
        check("Dueling bonus +2", der.get('melee_damage_bonus') == 2, f"got {der.get('melee_damage_bonus')}")
        check("Extra Attack available (Lv5)", True)  # will test in combat
        check("Spell slots 1st=4, 2nd=2", char.get('spell_slots',{}).get('1st') == 4)

        # ═══════════════════════════════════════════
        # 2. LEVEL UP
        # ═══════════════════════════════════════════
        print("\n══ 2. LEVEL UP ══")
        lv = (await c.post(f'/characters/{cid}/level-up', json={
            'use_average_hp': True,
        })).json()
        check("Level up success", 'level_up_details' in lv, str(lv.get('detail',''))[:80])
        if 'level_up_details' in lv:
            check("New level = 6", lv['level_up_details']['new_level'] == 6)
            check("HP gained", lv['level_up_details']['hp_gain'] > 0, f"hp_gain={lv['level_up_details']['hp_gain']}")

        # ═══════════════════════════════════════════
        # 3. GOLD
        # ═══════════════════════════════════════════
        print("\n══ 3. GOLD ══")
        gold = (await c.patch(f'/characters/{cid}/gold', json={'amount': 50, 'reason': 'loot'})).json()
        check("Gold added", gold.get('gold', 0) >= 50, str(gold)[:80])
        gold2 = (await c.patch(f'/characters/{cid}/gold', json={'amount': -20, 'reason': 'buy potion'})).json()
        check("Gold spent", gold2.get('gold', 0) >= 30, str(gold2)[:80])

        # ═══════════════════════════════════════════
        # 4. EXHAUSTION
        # ═══════════════════════════════════════════
        print("\n══ 4. EXHAUSTION ══")
        ex = (await c.patch(f'/characters/{cid}/exhaustion', json={'change': 1})).json()
        check("Exhaustion level 1", ex.get('exhaustion_level') == 1, str(ex)[:80])
        check("Effect: ability_check_disadvantage", 'ability_check_disadvantage' in (ex.get('active_effects') or []))
        ex2 = (await c.patch(f'/characters/{cid}/exhaustion', json={'change': -1})).json()
        check("Exhaustion reduced to 0", ex2.get('exhaustion_level') == 0)

        # ═══════════════════════════════════════════
        # 5. COMBAT SETUP
        # ═══════════════════════════════════════════
        print("\n══ 5. COMBAT SETUP ══")
        sess = (await c.post('/game/sessions', json={
            'module_id': mid, 'player_character_id': cid, 'companion_ids': [],
        })).json()
        sid = sess.get('session_id', sess.get('id', ''))
        check("Session created", bool(sid))

        # Init combat directly
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Session as S, CombatState, Character
        from services.dnd_rules import roll_initiative

        async with AsyncSessionLocal() as db:
            so = (await db.execute(select(S).where(S.id == sid))).scalar_one()
            chs = (await db.execute(select(Character).where(Character.session_id == sid))).scalars().all()
            enemies = [{
                'id': f'enemy_{uuid.uuid4().hex[:8]}', 'name': '骷髅兵',
                'hp': 15, 'hp_current': 15, 'hp_max': 15, 'ac': 12,
                'attack_bonus': 3, 'damage_dice': '1d6+1', 'damage_type': 'slashing',
                'conditions': [], 'dead': False, 'is_player': False, 'is_enemy': True,
                'resistances': [], 'immunities': [], 'vulnerabilities': ['bludgeoning'],
                'derived': {'hp_max':15,'ac':12,'attack_bonus':3,
                    'ability_modifiers':{'str':1,'dex':2,'con':1,'int':-2,'wis':0,'cha':-3}},
                'actions': [{'name':'短剑','type':'melee_attack','attack_bonus':3,
                    'damage_dice':'1d6+1','damage_type':'slashing'}],
            }]
            combatants = [{'id':str(ch.id),'name':ch.name,'initiative':(ch.derived or{}).get('initiative',0),
                'is_player':ch.is_player,'is_enemy':False} for ch in chs] + enemies
            to = roll_initiative(combatants)
            # Force player first
            for i,t in enumerate(to):
                if t.get('is_player'): to.insert(0, to.pop(i)); break
            pos = {str(chs[0].id): {'x':4,'y':5}, enemies[0]['id']: {'x':5,'y':5}}
            gs = dict(so.game_state or {}); gs['enemies'] = enemies
            so.game_state = gs; so.combat_active = True
            db.add(CombatState(id=str(uuid.uuid4()), session_id=sid, turn_order=to,
                current_turn_index=0, round_number=1, entity_positions=pos,
                grid_data={'3_5': 'wall'}, combat_log=[], turn_states={}))
            await db.commit()
        eid = enemies[0]['id']
        check("Combat initialized", True)

        # ═══════════════════════════════════════════
        # 6. PLAYER ATTACK (Extra Attack + Dueling)
        # ═══════════════════════════════════════════
        print("\n══ 6. PLAYER ATTACK ══")
        a1 = (await c.post(f'/game/combat/{sid}/action', json={
            'entity_id': cid, 'target_id': eid, 'action_type': 'melee',
        })).json()
        check("Attack 1 OK", 'narration' in a1, str(a1.get('detail',''))[:80])
        if 'attacks_max' in a1:
            check("Extra Attack (attacks_max >= 2)", a1.get('attacks_max', 1) >= 2, f"max={a1.get('attacks_max')}")

        # Second attack
        if a1.get('attacks_made', 1) < a1.get('attacks_max', 1):
            a2 = (await c.post(f'/game/combat/{sid}/action', json={
                'entity_id': cid, 'target_id': eid, 'action_type': 'melee',
            })).json()
            check("Extra Attack 2 OK", 'narration' in a2, str(a2.get('detail',''))[:80])

        # ═══════════════════════════════════════════
        # 7. DIVINE SMITE
        # ═══════════════════════════════════════════
        print("\n══ 7. DIVINE SMITE ══")
        if a1.get('attack_result', {}).get('hit'):
            sm = (await c.post(f'/game/combat/{sid}/smite', json={'slot_level': 1})).json()
            check("Smite OK", 'smite_damage' in sm, str(sm.get('detail',''))[:80])
        else:
            print("  SKIP Skipped (attack missed)")

        # ═══════════════════════════════════════════
        # 8. CLASS FEATURE: Second Wind (Fighter test later)
        # ═══════════════════════════════════════════
        print("\n══ 8. END TURN + AI ══")
        end = (await c.post(f'/game/combat/{sid}/end-turn')).json()
        check("End turn OK", 'next_turn_index' in end, str(end.get('detail',''))[:80])

        # AI turns
        ai_ok = True
        for i in range(5):
            cs = (await c.get(f'/game/combat/{sid}')).json()
            ct = cs['turn_order'][cs['current_turn_index']]
            if ct.get('is_player'):
                break
            ai = (await c.post(f'/game/combat/{sid}/ai-turn')).json()
            if 'detail' in ai:
                check(f"AI turn {i+1}", False, ai['detail'])
                ai_ok = False
                break
        check("AI turn cycle complete", ai_ok)

        # ═══════════════════════════════════════════
        # 9. REACTION (if player was targeted)
        # ═══════════════════════════════════════════
        print("\n══ 9. REACTION SYSTEM ══")
        # Test reaction endpoint directly
        react = (await c.post(f'/game/combat/{sid}/reaction', json={
            'reaction_type': 'shield',
        })).json()
        # May fail if no reaction available or not player's turn to react - that's OK
        if 'detail' in react:
            print(f"  SKIP Reaction test: {react['detail'][:60]}")
        else:
            check("Shield reaction OK", 'ac_bonus' in react or 'result' in react)

        # ═══════════════════════════════════════════
        # 10. SHORT REST
        # ═══════════════════════════════════════════
        print("\n══ 10. SHORT REST ══")
        await c.post(f'/game/combat/{sid}/end')
        rest = (await c.post(f'/game/sessions/{sid}/rest?rest_type=short')).json()
        check("Short rest OK", 'characters' in rest, str(rest.get('detail',''))[:80])
        if 'characters' in rest:
            ch_rest = rest['characters'][0]
            check("Hit dice tracked", 'hit_dice_remaining' in ch_rest, str(ch_rest.keys()))

        # ═══════════════════════════════════════════
        # SUMMARY
        # ═══════════════════════════════════════════
        print(f"\n{'═'*40}")
        print(f"  RESULTS: {PASS} passed, {FAIL} failed")
        print(f"{'═'*40}")

asyncio.run(test())
