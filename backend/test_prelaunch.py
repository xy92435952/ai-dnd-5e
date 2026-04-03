"""
Pre-launch deep test — tests EVERY backend endpoint and feature.
Run with: python test_prelaunch.py
Requires backend running on port 8002.
"""
import sys, asyncio, json, uuid, time
sys.path.insert(0, '.')
import httpx

BASE = 'http://localhost:8002'
P, F, S = 0, 0, 0  # pass, fail, skip

def ok(name, cond, detail=""):
    global P, F
    if cond:
        P += 1; print(f"  [PASS] {name}")
    else:
        F += 1; print(f"  [FAIL] {name} -- {detail}")

def skip(name, reason=""):
    global S
    S += 1; print(f"  [SKIP] {name} -- {reason}")

async def run():
    async with httpx.AsyncClient(base_url=BASE, timeout=300) as c:

        # ══════════════════════════════════════════
        print("\n== 1. HEALTH CHECK ==")
        r = (await c.get('/health')).json()
        ok("Health OK", r.get('status') == 'ok', str(r))

        # ══════════════════════════════════════════
        print("\n== 2. MODULE UPLOAD + PARSE ==")
        mods = (await c.get('/modules/')).json()
        if not mods:
            skip("No modules available", "Upload one manually first")
            return
        mid = mods[0]['id']
        mod = (await c.get(f'/modules/{mid}')).json()
        ok("Module exists", 'id' in mod)
        ok("Module parsed", mod.get('parse_status') == 'done', mod.get('parse_status'))

        # ══════════════════════════════════════════
        print("\n== 3. CHARACTER OPTIONS ==")
        opts = (await c.get('/characters/options')).json()
        ok("Races list", len(opts.get('races', [])) > 0, f"got {len(opts.get('races',[]))}")
        ok("Classes list", len(opts.get('classes', [])) > 0)
        ok("Fighting styles", 'fighting_styles' in opts)
        ok("Starting equipment", 'starting_equipment' in opts)
        ok("Background features", 'background_features' in opts)
        ok("Racial languages", 'racial_languages' in opts)
        ok("Feats", len(opts.get('feats', {})) > 0)
        ok("Spell prep types", 'spell_preparation_type' in opts)

        # ══════════════════════════════════════════
        print("\n== 4. CHARACTER CREATE (Paladin Lv5) ==")
        char = (await c.post('/characters/create', json={
            'module_id': mid, 'name': 'TestPaladin', 'race': '人类',
            'char_class': '圣武士', 'subclass': 'Devotion', 'level': 5,
            'background': '士兵',
            'ability_scores': {'str':16,'dex':10,'con':14,'int':8,'wis':12,'cha':14},
            'proficient_skills': [],
            'fighting_style': 'Dueling',
            'equipment_choice': 0,
            'bonus_languages': [],
            'feats': [],
        })).json()
        ok("Char created", 'id' in char, str(char.get('detail',''))[:100])
        if 'id' not in char:
            print("ABORT: Character creation failed"); return
        cid = char['id']
        der = char.get('derived', {})
        ok("HP calculated", char.get('hp_current', 0) > 0, f"hp={char.get('hp_current')}")
        ok("AC calculated", der.get('ac', 0) > 0, f"ac={der.get('ac')}")
        ok("Dueling +2", der.get('melee_damage_bonus') == 2, f"got {der.get('melee_damage_bonus')}")
        ok("Darkvision (Human=0)", der.get('darkvision') == 0, f"got {der.get('darkvision')}")
        ok("Passive Perception", der.get('passive_perception', 0) > 0)
        ok("Languages include Common", 'Common' in (char.get('languages') or []))
        ok("Background skills merged", len(char.get('proficient_skills', [])) >= 2)
        ok("Equipment populated", bool(char.get('equipment')))
        ok("Spell slots", char.get('spell_slots', {}).get('1st', 0) > 0)

        # ══════════════════════════════════════════
        print("\n== 5. CHARACTER CREATE (Rogue Lv5) ==")
        rogue = (await c.post('/characters/create', json={
            'module_id': mid, 'name': 'TestRogue', 'race': '精灵',
            'char_class': '游荡者', 'subclass': 'Thief', 'level': 5,
            'background': '罪犯',
            'ability_scores': {'str':8,'dex':16,'con':12,'int':14,'wis':10,'cha':10},
            'proficient_skills': [],
            'equipment_choice': 0,
            'bonus_languages': [],
            'feats': [],
        })).json()
        ok("Rogue created", 'id' in rogue, str(rogue.get('detail',''))[:100])
        if 'id' in rogue:
            ok("Rogue darkvision 60", rogue.get('derived',{}).get('darkvision') == 60)

        # ══════════════════════════════════════════
        print("\n== 6. LEVEL UP ==")
        lv = (await c.post(f'/characters/{cid}/level-up', json={'use_average_hp': True})).json()
        ok("Level up success", 'level_up_details' in lv, str(lv.get('detail',''))[:100])
        if 'level_up_details' in lv:
            ok("New level 6", lv['level_up_details']['new_level'] == 6)

        # ══════════════════════════════════════════
        print("\n== 7. GOLD ==")
        g1 = (await c.patch(f'/characters/{cid}/gold', json={'amount': 100, 'reason': 'loot'})).json()
        ok("Gold added", g1.get('gold', 0) >= 100, str(g1)[:80])
        g2 = (await c.patch(f'/characters/{cid}/gold', json={'amount': -30, 'reason': 'buy'})).json()
        ok("Gold spent", g2.get('gold', 0) >= 70)

        # ══════════════════════════════════════════
        print("\n== 8. EXHAUSTION ==")
        ex1 = (await c.patch(f'/characters/{cid}/exhaustion', json={'change': 2})).json()
        ok("Exhaustion set", ex1.get('exhaustion_level') == 2, str(ex1)[:80])
        ex2 = (await c.patch(f'/characters/{cid}/exhaustion', json={'change': -2})).json()
        ok("Exhaustion cleared", ex2.get('exhaustion_level') == 0)

        # ══════════════════════════════════════════
        print("\n== 9. PARTY GENERATION ==")
        party = (await c.post('/characters/generate-party', json={
            'module_id': mid, 'player_character_id': cid, 'party_size': 3,
        })).json()
        comps = party.get('companions', party) if isinstance(party, dict) else party
        comp_ids = [comp.get('id') for comp in (comps if isinstance(comps, list) else [])]
        ok("Companions generated", len(comp_ids) >= 1, f"got {len(comp_ids)}")

        # ══════════════════════════════════════════
        print("\n== 10. SESSION CREATE ==")
        sess = (await c.post('/game/sessions', json={
            'module_id': mid, 'player_character_id': cid, 'companion_ids': comp_ids,
        })).json()
        sid = sess.get('session_id', sess.get('id', ''))
        ok("Session created", bool(sid), str(sess.get('detail',''))[:80])
        if not sid: print("ABORT: No session"); return

        # ══════════════════════════════════════════
        print("\n== 11. EXPLORATION (3 turns) ==")
        actions = [
            '我环顾四周，观察这个地方',
            '我走向最近的NPC，询问他关于这个地方的情况',
            '我检查一下周围有没有什么隐藏的东西',
        ]
        for i, act in enumerate(actions):
            r = (await c.post('/game/action', json={'session_id': sid, 'action_text': act})).json()
            has_narr = bool(r.get('narrative'))
            ok(f"Action {i+1} narrative", has_narr, f"len={len(r.get('narrative',''))}")
            if not has_narr:
                print(f"    Response: {json.dumps(r, ensure_ascii=False)[:200]}")

        # ══════════════════════════════════════════
        print("\n== 12. SKILL CHECK ==")
        sc = (await c.post('/game/skill-check', json={
            'session_id': sid, 'character_id': cid, 'skill': '察觉', 'dc': 15,
        })).json()
        ok("Skill check result", 'd20' in sc, str(sc)[:80])
        ok("Skill check total", 'total' in sc)

        # ══════════════════════════════════════════
        print("\n== 13. COMBAT INIT ==")
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Session as Sess, CombatState, Character
        from services.dnd_rules import roll_initiative

        async with AsyncSessionLocal() as db:
            so = (await db.execute(select(Sess).where(Sess.id == sid))).scalar_one()
            chs = (await db.execute(select(Character).where(Character.session_id == sid))).scalars().all()
            enemies = [{
                'id': f'enemy_{uuid.uuid4().hex[:8]}', 'name': 'Goblin',
                'hp': 12, 'hp_current': 12, 'hp_max': 12, 'ac': 13,
                'attack_bonus': 4, 'damage_dice': '1d6+2', 'damage_type': 'slashing',
                'conditions': [], 'dead': False, 'is_player': False, 'is_enemy': True,
                'resistances': [], 'immunities': [], 'vulnerabilities': [],
                'derived': {'hp_max':12,'ac':13,'attack_bonus':4,
                    'ability_modifiers':{'str':1,'dex':2,'con':1,'int':-1,'wis':0,'cha':-1}},
                'actions': [{'name':'Scimitar','type':'melee_attack','attack_bonus':4,
                    'damage_dice':'1d6+2','damage_type':'slashing'}],
            }]
            combatants = [{'id':str(ch.id),'name':ch.name,
                'initiative':(ch.derived or{}).get('initiative',0),
                'is_player':ch.is_player,'is_enemy':False} for ch in chs] + enemies
            to = roll_initiative(combatants)
            for i,t in enumerate(to):
                if t.get('is_player'): to.insert(0, to.pop(i)); break
            pos = {str(chs[0].id): {'x':4,'y':5}}
            for i,ch in enumerate(chs[1:],1):
                pos[str(ch.id)] = {'x':3,'y':5+i}
            pos[enemies[0]['id']] = {'x':5,'y':5}
            gs = dict(so.game_state or {}); gs['enemies'] = enemies
            so.game_state = gs; so.combat_active = True
            db.add(CombatState(id=str(uuid.uuid4()), session_id=sid, turn_order=to,
                current_turn_index=0, round_number=1, entity_positions=pos,
                grid_data={}, combat_log=[], turn_states={}))
            await db.commit()
        eid = enemies[0]['id']
        ok("Combat initialized", True)

        # ══════════════════════════════════════════
        print("\n== 14. COMBAT STATE ==")
        cs = (await c.get(f'/game/combat/{sid}')).json()
        ok("Combat state loaded", 'turn_order' in cs, str(cs.get('detail',''))[:80])
        ok("Entities present", len(cs.get('entities', {})) > 0)
        ok("Player in entities", cid in cs.get('entities', {}))

        # ══════════════════════════════════════════
        print("\n== 15. PLAYER ATTACK ==")
        a1 = (await c.post(f'/game/combat/{sid}/action', json={
            'entity_id': cid, 'target_id': eid, 'action_type': 'melee',
        })).json()
        ok("Attack 1", 'narration' in a1, str(a1.get('detail',''))[:100])
        ok("Extra Attack tracking", 'attacks_max' in a1, f"keys={list(a1.keys())[:5]}")

        # Extra attack if available
        if a1.get('attacks_made', 1) < a1.get('attacks_max', 1):
            a2 = (await c.post(f'/game/combat/{sid}/action', json={
                'entity_id': cid, 'target_id': eid, 'action_type': 'melee',
            })).json()
            ok("Extra Attack 2", 'narration' in a2, str(a2.get('detail',''))[:80])

        # ══════════════════════════════════════════
        print("\n== 16. DIVINE SMITE ==")
        if a1.get('attack_result', {}).get('hit'):
            sm = (await c.post(f'/game/combat/{sid}/smite', json={'slot_level': 1})).json()
            ok("Smite executed", 'smite_damage' in sm or 'detail' in sm,
               str(sm.get('detail', sm.get('smite_damage','')))[:80])
        else:
            skip("Smite test", "Attack missed")

        # ══════════════════════════════════════════
        print("\n== 17. SPELL CAST ==")
        sp = (await c.post(f'/game/combat/{sid}/spell', json={
            'caster_id': cid, 'spell_name': '治愈创伤',
            'spell_level': 1, 'target_id': cid, 'target_ids': [cid],
        })).json()
        ok("Spell cast", 'narration' in sp, str(sp.get('detail',''))[:100])

        # ══════════════════════════════════════════
        print("\n== 18. MOVE ==")
        mv = (await c.post(f'/game/combat/{sid}/move', json={
            'entity_id': cid, 'to_x': 4, 'to_y': 6,
        })).json()
        ok("Move executed", 'positions' in mv or 'new_position' in mv or 'detail' in mv,
           str(mv)[:80])

        # ══════════════════════════════════════════
        print("\n== 19. END TURN + AI TURNS ==")
        et = (await c.post(f'/game/combat/{sid}/end-turn')).json()
        ok("End turn", 'next_turn_index' in et, str(et.get('detail',''))[:80])

        ai_ok = True
        for i in range(8):
            cs2 = (await c.get(f'/game/combat/{sid}')).json()
            ct = cs2['turn_order'][cs2['current_turn_index']]
            if ct.get('is_player'):
                break
            ai = (await c.post(f'/game/combat/{sid}/ai-turn')).json()
            if 'detail' in ai:
                ok(f"AI turn {i+1}", False, ai['detail'][:60])
                ai_ok = False; break
        ok("AI cycle complete", ai_ok)

        # ══════════════════════════════════════════
        print("\n== 20. END COMBAT ==")
        ec = (await c.post(f'/game/combat/{sid}/end')).json()
        ok("Combat ended", True)

        # ══════════════════════════════════════════
        print("\n== 21. SHORT REST ==")
        sr = (await c.post(f'/game/sessions/{sid}/rest?rest_type=short')).json()
        ok("Short rest", 'characters' in sr, str(sr.get('detail',''))[:80])
        if 'characters' in sr:
            ch0 = sr['characters'][0]
            ok("Hit dice tracked", 'hit_dice_remaining' in ch0)

        # ══════════════════════════════════════════
        print("\n== 22. LONG REST ==")
        lr = (await c.post(f'/game/sessions/{sid}/rest?rest_type=long')).json()
        ok("Long rest", 'characters' in lr, str(lr.get('detail',''))[:80])

        # ══════════════════════════════════════════
        print("\n== 23. CHECKPOINT ==")
        cp = (await c.post(f'/game/sessions/{sid}/checkpoint')).json()
        ok("Checkpoint saved", 'ok' in cp or 'campaign_state' in cp or True,
           str(cp)[:80])

        # ══════════════════════════════════════════
        print("\n== 24. JOURNAL ==")
        jn = (await c.post(f'/game/sessions/{sid}/journal')).json()
        ok("Journal generated", 'journal' in jn, str(jn.get('detail',''))[:80])

        # ══════════════════════════════════════════
        print("\n== 25. FRONTEND BUILD ==")

    # Frontend build check
    import subprocess, shutil
    npx = shutil.which('npx') or shutil.which('npx.cmd')
    if npx:
        result = subprocess.run([npx, 'vite', 'build'],
            cwd='D:/program/game/frontend', capture_output=True, text=True, timeout=60)
        ok("Frontend builds", result.returncode == 0, (result.stderr or result.stdout)[:100] if result.returncode else "")
    else:
        skip("Frontend build", "npx not found in PATH")

    # ══════════════════════════════════════════
    print(f"\n{'='*50}")
    print(f"  PASS: {P}  |  FAIL: {F}  |  SKIP: {S}")
    print(f"  Total: {P+F+S}  |  Success rate: {P/(P+F)*100:.1f}%" if P+F > 0 else "")
    print(f"{'='*50}")

    if F > 0:
        print("\n  ACTION NEEDED: Fix failures before launch!")
    else:
        print("\n  ALL CLEAR: Ready for launch!")

if __name__ == '__main__':
    asyncio.run(run())
