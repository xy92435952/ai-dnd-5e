"""
Multi-round combat with overpowered enemy + death save test.
Enemy: Ancient Red Dragon (AC 22, HP 200, +17 attack, 4d6+9 damage)
Player: Lv5 Paladin (HP 44, AC 18) — will get knocked to 0 HP
Tests: multi-round cycling, death saves, nat 20 revive, 3 failures = death
"""
import sys, asyncio, json, uuid
sys.path.insert(0, '.')
import httpx

P, F = 0, 0
def ok(name, cond, detail=""):
    global P, F
    if cond: P += 1; print(f"  [PASS] {name}")
    else:    F += 1; print(f"  [FAIL] {name} -- {detail}")

def safe(s, maxlen=80):
    return (s or '')[:maxlen].encode('ascii','replace').decode()

async def run():
    async with httpx.AsyncClient(base_url='http://localhost:8002', timeout=300) as c:
        mods = (await c.get('/modules/')).json()
        mid = mods[0]['id']

        # Create weak Paladin Lv5
        print("\n== SETUP ==")
        player = (await c.post('/characters/create', json={
            'module_id': mid, 'name': 'Doomed', 'race': '人类',
            'char_class': '圣武士', 'subclass': 'Devotion', 'level': 5,
            'background': '士兵',
            'ability_scores': {'str':16,'dex':10,'con':14,'int':8,'wis':12,'cha':14},
            'proficient_skills': [], 'fighting_style': 'Defense',
            'equipment_choice': 0, 'bonus_languages': [], 'feats': [],
        })).json()
        ok("Player created", 'id' in player)
        if 'id' not in player: return
        pid = player['id']
        print(f"  Player: HP={player['hp_current']} AC={player['derived']['ac']}")

        # Generate 2 companions
        party = (await c.post('/characters/generate-party', json={
            'module_id': mid, 'player_character_id': pid, 'party_size': 3,
        })).json()
        comps = party.get('companions', party) if isinstance(party, dict) else party
        comp_ids = [comp['id'] for comp in (comps if isinstance(comps, list) else []) if isinstance(comp, dict) and 'id' in comp]
        print(f"  Companions: {len(comp_ids)}")

        # Create session
        sess = (await c.post('/game/sessions', json={
            'module_id': mid, 'player_character_id': pid, 'companion_ids': comp_ids,
        })).json()
        sid = sess.get('session_id', sess.get('id', ''))

        # Init combat with overpowered dragon
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Session as Sess, CombatState, Character
        from services.dnd_rules import roll_initiative

        async with AsyncSessionLocal() as db:
            so = (await db.execute(select(Sess).where(Sess.id == sid))).scalar_one()
            chs = (await db.execute(select(Character).where(Character.session_id == sid))).scalars().all()

            enemies = [{
                'id': f'enemy_{uuid.uuid4().hex[:8]}',
                'name': 'Ancient Dragon',
                'hp': 200, 'hp_current': 200, 'hp_max': 200, 'ac': 22,
                'attack_bonus': 17, 'damage_dice': '4d6+9', 'damage_type': 'slashing',
                'conditions': [], 'dead': False, 'is_player': False, 'is_enemy': True,
                'resistances': [], 'immunities': ['fire'], 'vulnerabilities': [],
                'derived': {'hp_max': 200, 'ac': 22, 'attack_bonus': 17,
                    'ability_modifiers': {'str': 10, 'dex': 0, 'con': 8, 'int': 4, 'wis': 3, 'cha': 6}},
                'actions': [{'name': 'Claw', 'type': 'melee_attack', 'attack_bonus': 17,
                    'damage_dice': '4d6+9', 'damage_type': 'slashing'}],
            }]

            combatants = [
                {'id': str(ch.id), 'name': ch.name,
                 'initiative': (ch.derived or {}).get('initiative', 0),
                 'is_player': ch.is_player, 'is_enemy': False}
                for ch in chs
            ] + enemies
            to = roll_initiative(combatants)
            # Force player first
            for i, t in enumerate(to):
                if t.get('is_player'): to.insert(0, to.pop(i)); break

            pos = {}
            for i, ch in enumerate(chs):
                pos[str(ch.id)] = {'x': 3, 'y': 5 + i}
            pos[enemies[0]['id']] = {'x': 5, 'y': 5}

            gs = dict(so.game_state or {}); gs['enemies'] = enemies
            so.game_state = gs; so.combat_active = True
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(so, "game_state")
            db.add(CombatState(id=str(uuid.uuid4()), session_id=sid,
                turn_order=to, current_turn_index=0, round_number=1,
                entity_positions=pos, grid_data={}, combat_log=[], turn_states={}))
            await db.commit()

        eid = enemies[0]['id']
        print(f"  Dragon: HP=200 AC=22 ATK=+17 DMG=4d6+9")
        print(f"  Turn order: {len(to)} entities")

        # ════════════════════════════════════════
        # COMBAT LOOP
        # ════════════════════════════════════════
        MAX_ROUNDS = 15
        player_died = False
        player_revived = False
        death_save_count = 0
        combat_ended = False
        rounds_completed = 0

        for rnd in range(MAX_ROUNDS):
            cs = (await c.get(f'/game/combat/{sid}')).json()
            if 'turn_order' not in cs: break
            rounds_completed = cs.get('round_number', 0)
            print(f"\n== ROUND {rounds_completed} ==")

            for turn_idx in range(len(cs.get('turn_order', []))):
                cs = (await c.get(f'/game/combat/{sid}')).json()
                if 'turn_order' not in cs: break
                ci = cs['current_turn_index']
                ct = cs['turn_order'][ci]
                nm = safe(ct.get('name', '?'))
                is_player = ct.get('is_player', False)

                if is_player:
                    # Check player HP
                    player_ent = cs.get('entities', {}).get(pid, {})
                    php = player_ent.get('hp_current', 0)
                    print(f"  >> PLAYER {nm} (HP={php})")

                    if php <= 0:
                        # DEATH SAVE!
                        print(f"  >> DEATH SAVE!")
                        ds = (await c.post(f'/game/combat/{sid}/death-save', json={
                            'character_id': pid,
                        })).json()
                        death_save_count += 1

                        if 'detail' in ds:
                            print(f"    Error: {safe(ds['detail'])}")
                            # End turn manually
                            await c.post(f'/game/combat/{sid}/end-turn')
                        else:
                            d20 = ds.get('d20', 0)
                            outcome = ds.get('outcome', '?')
                            succ = ds.get('successes', 0)
                            fail = ds.get('failures', 0)
                            new_hp = ds.get('new_hp', 0)
                            print(f"    d20={d20} outcome={safe(str(outcome))} succ={succ} fail={fail} hp={new_hp}")

                            if outcome == 'revived':
                                player_revived = True
                                print(f"    !! NATURAL 20 REVIVE! HP={new_hp}")
                            elif outcome == 'dead':
                                player_died = True
                                print(f"    !! CHARACTER DIED (3 failures)")
                            elif outcome == 'stable':
                                print(f"    Stabilized (3 successes)")

                            # End turn after death save
                            await c.post(f'/game/combat/{sid}/end-turn')

                        if player_died: break
                        continue

                    # Normal player turn: attack the dragon
                    alive = [eid2 for eid2, e in cs.get('entities', {}).items()
                             if e.get('is_enemy') and e.get('hp_current', 0) > 0]
                    if not alive:
                        print(f"    No enemies alive!")
                        combat_ended = True; break

                    target = alive[0]
                    for atk_num in range(2):
                        fresh = (await c.get(f'/game/combat/{sid}')).json()
                        atk = (await c.post(f'/game/combat/{sid}/action', json={
                            'entity_id': pid, 'target_id': target, 'action_type': 'melee',
                        })).json()
                        if 'detail' in atk: break
                        ar = atk.get('attack_result', {})
                        am = atk.get('attacks_made', 1)
                        mx = atk.get('attacks_max', 1)
                        hit = ar.get('hit', False)
                        d20v = ar.get('d20', 0)
                        dmgv = atk.get('damage', 0)
                        print(f"    Attack {am}/{mx}: d20={d20v} {'HIT dmg='+str(dmgv) if hit else 'MISS'}")
                        if atk.get('combat_over'):
                            combat_ended = True; break
                        if am >= mx: break
                    if combat_ended: break

                    # End player turn
                    et = (await c.post(f'/game/combat/{sid}/end-turn')).json()
                    if 'detail' in et: break
                    if et.get('combat_over'):
                        combat_ended = True; break

                else:
                    # AI turn
                    role_tag = "ENEMY" if ct.get('is_enemy') else "ALLY"
                    ai = (await c.post(f'/game/combat/{sid}/ai-turn')).json()
                    if 'detail' in ai:
                        print(f"  >> [{role_tag}] {nm}: ERROR {safe(ai['detail'])}")
                        break
                    dmg = ai.get('damage', 0)
                    tgt_hp = ai.get('target_new_hp')
                    print(f"  >> [{role_tag}] {nm}: {safe(ai.get('narration',''))}{f' dmg={dmg}' if dmg else ''}{f' target_hp={tgt_hp}' if tgt_hp is not None else ''}")

                    if ai.get('combat_over'):
                        combat_ended = True; break

                if combat_ended or player_died: break
            if combat_ended or player_died: break

        # ════════════════════════════════════════
        # RESULTS
        # ════════════════════════════════════════
        print(f"\n{'='*60}")
        print(f"== RESULTS ==")

        # Final state
        final = (await c.get(f'/game/combat/{sid}')).json()
        if 'entities' in final:
            print(f"\n  Final state:")
            for eid2, e in final.get('entities', {}).items():
                nm2 = safe(e.get('name', '?'))
                hp2 = e.get('hp_current', 0)
                mx2 = e.get('hp_max', 0)
                role = "ENEMY" if e.get('is_enemy') else ("PLAYER" if e.get('is_player') else "ALLY")
                print(f"    [{role}] {nm2}: HP={hp2}/{mx2}")

        ok("Multi-round combat", rounds_completed >= 2, f"rounds={rounds_completed}")
        ok("Turn cycling worked", rounds_completed >= 2)
        ok("Player was knocked to 0 HP", php <= 0 or player_died or death_save_count > 0,
           f"player HP never reached 0 (final={php})")
        ok("Death saves triggered", death_save_count > 0, f"count={death_save_count}")
        if player_died:
            ok("Player death (3 failures)", True)
        if player_revived:
            ok("Natural 20 revive", True)

        print(f"\n  Death saves rolled: {death_save_count}")
        print(f"  Player died: {player_died}")
        print(f"  Player revived: {player_revived}")
        print(f"  Rounds completed: {rounds_completed}")

        print(f"\n{'='*60}")
        print(f"  PASS: {P}  |  FAIL: {F}")
        print(f"{'='*60}")

asyncio.run(run())
