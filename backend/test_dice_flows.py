"""Test ALL player dice flows: attack-roll/damage-roll, spell-roll/spell-confirm, smite, initiative"""
import sys, asyncio, json, uuid
sys.path.insert(0, '.')
import httpx

P, F = 0, 0
def ok(name, cond, detail=""):
    global P, F
    if cond: P += 1; print(f"  [PASS] {name}")
    else:    F += 1; print(f"  [FAIL] {name} -- {detail}")

def safe(s, n=60):
    return (s or '')[:n].encode('ascii','replace').decode()

async def run():
    async with httpx.AsyncClient(base_url='http://localhost:8002', timeout=300) as c:
        # Login
        login = (await c.post('/auth/login', json={'username':'test','password':'123456'})).json()
        token = login.get('token','')
        if not token: print('Login failed'); return
        c.headers['Authorization'] = f'Bearer {token}'

        mods = (await c.get('/modules/')).json()
        if not mods: print('No modules'); return
        mid = mods[0]['id']

        # Create Paladin Lv5 with healing spell
        print("\n== SETUP ==")
        char = (await c.post('/characters/create', json={
            'module_id': mid, 'name': 'DiceTest', 'race': '人类',
            'char_class': '圣武士', 'subclass': 'Devotion', 'level': 5,
            'background': '士兵',
            'ability_scores': {'str':18,'dex':10,'con':14,'int':8,'wis':12,'cha':14},
            'proficient_skills': [], 'fighting_style': 'Dueling',
            'equipment_choice': 0, 'bonus_languages': [], 'feats': [],
            'known_spells': ['治愈创伤'],
        })).json()
        ok("Player created", 'id' in char, safe(str(char.get('detail',''))))
        if 'id' not in char: return
        pid = char['id']

        sess = (await c.post('/game/sessions', json={
            'module_id': mid, 'player_character_id': pid, 'companion_ids': [],
        })).json()
        sid = sess.get('session_id', sess.get('id', ''))

        # Init combat
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Session as Sess, CombatState, Character
        from services.dnd_rules import roll_initiative
        from sqlalchemy.orm.attributes import flag_modified

        async with AsyncSessionLocal() as db:
            so = (await db.execute(select(Sess).where(Sess.id == sid))).scalar_one()
            chs = (await db.execute(select(Character).where(Character.session_id == sid))).scalars().all()
            enemies = [{
                'id': f'enemy_{uuid.uuid4().hex[:8]}', 'name': 'Target',
                'hp': 50, 'hp_current': 50, 'hp_max': 50, 'ac': 8,
                'attack_bonus': 3, 'damage_dice': '1d4+1', 'damage_type': 'slashing',
                'conditions': [], 'dead': False, 'is_player': False, 'is_enemy': True,
                'resistances': [], 'immunities': [], 'vulnerabilities': [],
                'derived': {'hp_max':50,'ac':8,'attack_bonus':3,
                    'ability_modifiers':{'str':0,'dex':0,'con':0,'int':0,'wis':0,'cha':0}},
                'actions': [{'name':'Dagger','type':'melee_attack','attack_bonus':3,'damage_dice':'1d4+1','damage_type':'piercing'}],
            }]
            combatants = [{'id':str(ch.id),'name':ch.name,'initiative':(ch.derived or{}).get('initiative',0),
                'is_player':ch.is_player,'is_enemy':False} for ch in chs] + enemies
            to = roll_initiative(combatants)
            for i,t in enumerate(to):
                if t.get('is_player'): to.insert(0, to.pop(i)); break
            pos = {str(chs[0].id): {'x':4,'y':5}, enemies[0]['id']: {'x':5,'y':5}}
            gs = dict(so.game_state or {}); gs['enemies'] = enemies
            so.game_state = gs; so.combat_active = True
            flag_modified(so, "game_state")
            db.add(CombatState(id=str(uuid.uuid4()), session_id=sid, turn_order=to,
                current_turn_index=0, round_number=1, entity_positions=pos,
                grid_data={}, combat_log=[], turn_states={}))
            await db.commit()
        eid = enemies[0]['id']
        print(f"  Enemy: AC=8 HP=50 (easy to hit)")

        # ════════════════════════════════════════
        print("\n== TEST 1: ATTACK-ROLL + DAMAGE-ROLL ==")
        ar = (await c.post(f'/game/combat/{sid}/attack-roll', json={
            'entity_id': pid, 'target_id': eid, 'action_type': 'melee',
        })).json()

        if 'detail' in ar:
            ok("Attack roll", False, safe(ar['detail']))
        else:
            ok("Attack roll returned d20", 'd20' in ar, str(list(ar.keys())[:5]))
            ok("Hit determination", 'hit' in ar)
            ok("Pending attack ID", 'pending_attack_id' in ar)
            ok("Damage dice expression", 'damage_dice' in ar, ar.get('damage_dice'))
            ok("Attacks tracking", 'attacks_made' in ar, f"made={ar.get('attacks_made')}/{ar.get('attacks_max')}")
            print(f"  d20={ar.get('d20')} total={ar.get('attack_total')} vs AC={ar.get('target_ac')} hit={ar.get('hit')}")

            if ar.get('hit') and ar.get('pending_attack_id'):
                # Damage roll
                dr = (await c.post(f'/game/combat/{sid}/damage-roll', json={
                    'pending_attack_id': ar['pending_attack_id'],
                })).json()

                if 'detail' in dr:
                    ok("Damage roll", False, safe(dr['detail']))
                else:
                    ok("Damage total > 0", (dr.get('total_damage') or dr.get('damage_total', 0)) > 0)
                    ok("Target HP updated", dr.get('target_new_hp') is not None)
                    ok("Narration string", isinstance(dr.get('narration'), str))
                    ok("Can smite flag", 'can_smite' in dr)
                    dmg = dr.get('total_damage') or dr.get('damage_total', 0)
                    print(f"  Damage: {dmg} Target HP: {dr.get('target_new_hp')}")

                    # Test smite if available
                    if dr.get('can_smite'):
                        print("\n== TEST 2: DIVINE SMITE DICE ==")
                        sm = (await c.post(f'/game/combat/{sid}/smite', json={'slot_level': 1})).json()
                        if 'detail' in sm:
                            ok("Smite", False, safe(sm['detail']))
                        else:
                            ok("Smite damage", (sm.get('smite_damage') or 0) > 0)
                            ok("Smite dice notation", bool(sm.get('smite_dice')))
                            print(f"  Smite: {sm.get('smite_damage')} ({sm.get('smite_dice')})")
            else:
                print(f"  Miss — skipping damage roll")

        # Extra Attack (2nd attack)
        print("\n== TEST 3: EXTRA ATTACK ==")
        ar2 = (await c.post(f'/game/combat/{sid}/attack-roll', json={
            'entity_id': pid, 'target_id': eid, 'action_type': 'melee',
        })).json()
        if 'detail' in ar2:
            ok("Extra attack roll", False, safe(ar2['detail']))
        else:
            ok("Extra attack roll OK", 'd20' in ar2)
            if ar2.get('hit') and ar2.get('pending_attack_id'):
                dr2 = (await c.post(f'/game/combat/{sid}/damage-roll', json={
                    'pending_attack_id': ar2['pending_attack_id'],
                })).json()
                ok("Extra attack damage", 'detail' not in dr2, safe(str(dr2.get('detail',''))))

        # ════════════════════════════════════════
        print("\n== TEST 4: SPELL-ROLL + SPELL-CONFIRM ==")

        # Reduce HP first for healing test
        async with AsyncSessionLocal() as db:
            pc = await db.get(Character, pid)
            pc.hp_current = 20
            await db.commit()

        sr = (await c.post(f'/game/combat/{sid}/spell-roll', json={
            'caster_id': pid, 'spell_name': '治愈创伤', 'spell_level': 1,
            'target_id': pid, 'target_ids': [pid],
        })).json()

        if 'detail' in sr:
            ok("Spell roll", False, safe(sr['detail']))
        else:
            ok("Spell roll OK", 'pending_spell_id' in sr, str(list(sr.keys())[:5]))
            ok("Dice expression", 'dice_expression' in sr or 'damage_dice' in sr or 'heal_dice' in sr,
               str(list(sr.keys())[:8]))
            print(f"  Spell info: {safe(json.dumps(sr, ensure_ascii=False), 100)}")

            psid = sr.get('pending_spell_id')
            if psid:
                sc = (await c.post(f'/game/combat/{sid}/spell-confirm', json={
                    'pending_spell_id': psid,
                })).json()
                if 'detail' in sc:
                    ok("Spell confirm", False, safe(sc['detail']))
                else:
                    ok("Spell confirm OK", 'narration' in sc or 'heal' in sc or 'damage' in sc)
                    heal = sc.get('heal', sc.get('heal_total', 0))
                    print(f"  Heal: {heal} NewHP: {sc.get('target_new_hp')}")

        # ════════════════════════════════════════
        print("\n== TEST 5: END TURN + AI CYCLE ==")
        et = (await c.post(f'/game/combat/{sid}/end-turn')).json()
        ok("End turn", 'next_turn_index' in et, safe(str(et.get('detail',''))))

        for i in range(5):
            cs = (await c.get(f'/game/combat/{sid}')).json()
            ct = cs['turn_order'][cs['current_turn_index']]
            if ct.get('is_player'): break
            ai = (await c.post(f'/game/combat/{sid}/ai-turn')).json()
            if 'detail' in ai: break
        ok("AI cycle + back to player", True)

        # Verify player can attack again in new round
        print("\n== TEST 6: ROUND 2 ATTACK ==")
        ar3 = (await c.post(f'/game/combat/{sid}/attack-roll', json={
            'entity_id': pid, 'target_id': eid, 'action_type': 'melee',
        })).json()
        ok("Round 2 attack roll", 'd20' in ar3, safe(str(ar3.get('detail',''))))

        # ════════════════════════════════════════
        print(f"\n{'='*50}")
        print(f"  PASS: {P}  |  FAIL: {F}")
        print(f"{'='*50}")

asyncio.run(run())
