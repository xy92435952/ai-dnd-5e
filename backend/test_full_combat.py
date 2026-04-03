"""
Full multi-round combat test with companions until combat ends.
Tests: turn cycling, Extra Attack, AI companions, AI enemies, end-turn, victory condition.
"""
import sys, asyncio, json, uuid
sys.path.insert(0, '.')
import httpx

P, F = 0, 0
def ok(name, cond, detail=""):
    global P, F
    if cond: P += 1; print(f"  [PASS] {name}")
    else:    F += 1; print(f"  [FAIL] {name} -- {detail}")

def safe(s, maxlen=60):
    return (s or '')[:maxlen].encode('ascii','replace').decode()

async def run():
    async with httpx.AsyncClient(base_url='http://localhost:8002', timeout=300) as c:
        mods = (await c.get('/modules/')).json()
        mid = mods[0]['id']

        # 1. Create player (Paladin Lv5)
        print("\n== SETUP: Create Party ==")
        player = (await c.post('/characters/create', json={
            'module_id': mid, 'name': 'Arthas', 'race': '人类',
            'char_class': '圣武士', 'subclass': 'Devotion', 'level': 5,
            'background': '士兵',
            'ability_scores': {'str':18,'dex':10,'con':14,'int':8,'wis':12,'cha':14},
            'proficient_skills': [], 'fighting_style': 'Dueling',
            'equipment_choice': 0, 'bonus_languages': [], 'feats': [],
            'known_spells': ['治愈创伤'],
        })).json()
        ok("Player created", 'id' in player, safe(str(player.get('detail',''))))
        if 'id' not in player: return
        pid = player['id']
        print(f"  Player: Arthas HP={player['hp_current']} AC={player['derived']['ac']}")

        # 2. Generate companions
        print("  Generating companions...")
        party = (await c.post('/characters/generate-party', json={
            'module_id': mid, 'player_character_id': pid, 'party_size': 3,
        })).json()
        comps = party.get('companions', party) if isinstance(party, dict) else party
        comp_ids = []
        if isinstance(comps, list):
            for comp in comps:
                if isinstance(comp, dict) and 'id' in comp:
                    comp_ids.append(comp['id'])
                    nm = safe(comp.get('name','?'))
                    cl = safe(comp.get('char_class','?'))
                    print(f"  Companion: {nm} ({cl}) HP={comp.get('hp_current','?')}")
        ok("Companions generated", len(comp_ids) >= 1, f"got {len(comp_ids)}")

        # 3. Create session
        sess = (await c.post('/game/sessions', json={
            'module_id': mid, 'player_character_id': pid, 'companion_ids': comp_ids,
        })).json()
        sid = sess.get('session_id', sess.get('id',''))
        ok("Session created", bool(sid))

        # 4. Init combat with 2 weak enemies
        print("\n== SETUP: Init Combat ==")
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Session as Sess, CombatState, Character
        from services.dnd_rules import roll_initiative

        async with AsyncSessionLocal() as db:
            so = (await db.execute(select(Sess).where(Sess.id == sid))).scalar_one()
            chs = (await db.execute(select(Character).where(Character.session_id == sid))).scalars().all()

            enemies = []
            for i in range(2):
                enemies.append({
                    'id': f'enemy_{uuid.uuid4().hex[:8]}',
                    'name': f'Goblin_{i+1}',
                    'hp': 10, 'hp_current': 10, 'hp_max': 10, 'ac': 10,
                    'attack_bonus': 3, 'damage_dice': '1d4+1', 'damage_type': 'slashing',
                    'conditions': [], 'dead': False, 'is_player': False, 'is_enemy': True,
                    'resistances': [], 'immunities': [], 'vulnerabilities': [],
                    'derived': {'hp_max':10,'ac':10,'attack_bonus':3,
                        'ability_modifiers':{'str':0,'dex':1,'con':0,'int':-1,'wis':0,'cha':-1}},
                    'actions': [{'name':'Dagger','type':'melee_attack','attack_bonus':3,
                        'damage_dice':'1d4+1','damage_type':'piercing'}],
                })

            combatants = [
                {'id':str(ch.id),'name':ch.name,
                 'initiative':(ch.derived or{}).get('initiative',0),
                 'is_player':ch.is_player,'is_enemy':False}
                for ch in chs
            ] + enemies
            to = roll_initiative(combatants)

            # Force player first for predictable testing
            for i,t in enumerate(to):
                if t.get('is_player'): to.insert(0, to.pop(i)); break

            pos = {}
            for i, ch in enumerate(chs):
                pos[str(ch.id)] = {'x': 3, 'y': 5 + i}
            for i, e in enumerate(enemies):
                pos[e['id']] = {'x': 5, 'y': 5 + i}

            gs = dict(so.game_state or {}); gs['enemies'] = enemies
            so.game_state = gs; so.combat_active = True
            db.add(CombatState(id=str(uuid.uuid4()), session_id=sid,
                turn_order=to, current_turn_index=0, round_number=1,
                entity_positions=pos, grid_data={}, combat_log=[], turn_states={}))
            await db.commit()

        print(f"  Enemies: {len(enemies)} goblins (HP=10 AC=10)")
        print(f"  Turn order:")
        for t in to:
            role = "PLAYER" if t.get('is_player') else ("ENEMY" if t.get('is_enemy') else "ALLY")
            nm = safe(t.get('name','?'))
            print(f"    [{role}] {nm} init={t.get('initiative')}")
        eid1, eid2 = enemies[0]['id'], enemies[1]['id']

        # ════════════════════════════════════════
        # COMBAT LOOP
        # ════════════════════════════════════════
        MAX_ROUNDS = 10
        combat_over = False
        outcome = None
        round_num = 0

        for rnd in range(MAX_ROUNDS):
            # Get current state
            cs = (await c.get(f'/game/combat/{sid}')).json()
            if 'detail' in cs:
                ok(f"Get combat state", False, cs['detail'][:60])
                break
            round_num = cs.get('round_number', 0)
            print(f"\n== ROUND {round_num} ==")

            # Process all turns in this round
            for turn_idx in range(len(to)):
                cs = (await c.get(f'/game/combat/{sid}')).json()
                if 'turn_order' not in cs: break
                ci = cs['current_turn_index']
                ct = cs['turn_order'][ci]
                nm = safe(ct.get('name','?'))
                is_player = ct.get('is_player', False)

                if is_player:
                    print(f"  >> Player turn: {nm}")
                    # Find alive enemy
                    all_ents = cs.get('entities',{})
                    alive_enemies = [eid for eid, e in all_ents.items()
                                     if e.get('is_enemy') and e.get('hp_current',0) > 0]
                    if not alive_enemies:
                        # Debug: show all entities
                        for eid2, e2 in all_ents.items():
                            print(f"    entity: {safe(e2.get('name','?'))} is_enemy={e2.get('is_enemy')} hp={e2.get('hp_current')}")
                        print(f"  No alive enemies found!")
                        break

                    target = alive_enemies[0]
                    tgt_name = safe(cs['entities'][target].get('name','?'))
                    tgt_hp = cs['entities'][target].get('hp_current',0)

                    # Attack (with Extra Attack)
                    for atk_num in range(2):
                        # 每次攻击前重新获取活着的敌人
                        fresh_cs = (await c.get(f'/game/combat/{sid}')).json()
                        fresh_alive = [eid for eid, e in fresh_cs.get('entities',{}).items()
                                       if e.get('is_enemy') and e.get('hp_current',0) > 0]
                        if not fresh_alive: break
                        target = fresh_alive[0]

                        atk = (await c.post(f'/game/combat/{sid}/action', json={
                            'entity_id': pid, 'target_id': target, 'action_type': 'melee',
                        })).json()

                        if 'detail' in atk:
                            print(f"    Attack error: {safe(atk['detail'])}")
                            break

                        ar = atk.get('attack_result', {})
                        hit = ar.get('hit', False)
                        d20 = ar.get('d20', 0)
                        dmg = atk.get('damage', 0)
                        am = atk.get('attacks_made', 1)
                        mx = atk.get('attacks_max', 1)
                        print(f"    Attack {am}/{mx}: d20={d20} {'HIT' if hit else 'MISS'}{f' dmg={dmg}' if hit else ''}")

                        if atk.get('combat_over'):
                            combat_over = True; outcome = atk.get('outcome')
                            break
                        if am >= mx:
                            break

                    if combat_over: break

                    # End player turn
                    et = (await c.post(f'/game/combat/{sid}/end-turn')).json()
                    if 'detail' in et:
                        ok(f"End turn R{round_num}", False, safe(et['detail']))
                        combat_over = True; break
                    if et.get('combat_over'):
                        combat_over = True; outcome = et.get('outcome'); break

                else:
                    # AI turn (companion or enemy)
                    role_tag = "ENEMY" if ct.get('is_enemy') else "ALLY"
                    ai = (await c.post(f'/game/combat/{sid}/ai-turn')).json()
                    if 'detail' in ai:
                        ok(f"AI turn {nm}", False, safe(ai['detail']))
                        # If it's "player turn" error, we're desynced
                        if 'player' in ai.get('detail','').lower():
                            combat_over = True
                        break
                    narr = safe(ai.get('narration',''))
                    dmg = ai.get('damage', 0)
                    print(f"  >> [{role_tag}] {nm}: {narr}{f' (dmg={dmg})' if dmg else ''}")

                    if ai.get('combat_over'):
                        combat_over = True; outcome = ai.get('outcome'); break

                if combat_over: break
            if combat_over: break

        # ════════════════════════════════════════
        # RESULTS
        # ════════════════════════════════════════
        print(f"\n== COMBAT RESULT ==")
        if combat_over:
            ok("Combat ended naturally", True)
            print(f"  Outcome: {outcome or 'unknown'}")
            print(f"  Rounds: {round_num}")
        else:
            ok("Combat ended in time", False, f"Ran {MAX_ROUNDS} rounds without resolution")

        # Check final state
        final_cs = (await c.get(f'/game/combat/{sid}')).json()
        if 'entities' in final_cs:
            print(f"\n  Final state:")
            for eid, e in final_cs.get('entities', {}).items():
                nm = safe(e.get('name','?'))
                hp = e.get('hp_current', 0)
                mx = e.get('hp_max', 0)
                role = "ENEMY" if e.get('is_enemy') else ("PLAYER" if e.get('is_player') else "ALLY")
                status = "DEAD" if hp <= 0 else f"HP={hp}/{mx}"
                print(f"    [{role}] {nm}: {status}")

        # Verify turn cycling worked
        ok("Multi-round combat", round_num >= 2, f"only got {round_num} rounds")
        ok("No stuck turns", combat_over or round_num >= 2)

        print(f"\n{'='*50}")
        print(f"  PASS: {P}  |  FAIL: {F}")
        print(f"{'='*50}")

asyncio.run(run())
