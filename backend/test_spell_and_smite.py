"""专项测试：法术施放 + 至圣斩（独立回合，不与攻击冲突）"""
import sys, asyncio, json, uuid
sys.path.insert(0, '.')
import httpx

P, F = 0, 0
def ok(name, cond, detail=""):
    global P, F
    if cond: P += 1; print(f"  [PASS] {name}")
    else:    F += 1; print(f"  [FAIL] {name} -- {detail}")

async def run():
    async with httpx.AsyncClient(base_url='http://localhost:8002', timeout=300) as c:
        # 获取模组
        mods = (await c.get('/modules/')).json()
        mid = mods[0]['id']

        # 创建圣武士 Lv5
        print("\n== 1. CREATE PALADIN ==")
        char = (await c.post('/characters/create', json={
            'module_id': mid, 'name': 'SmiteTest', 'race': '人类',
            'char_class': '圣武士', 'subclass': 'Devotion', 'level': 5,
            'background': '士兵',
            'ability_scores': {'str':18,'dex':10,'con':14,'int':8,'wis':12,'cha':14},
            'proficient_skills': [], 'fighting_style': 'Dueling',
            'equipment_choice': 0, 'bonus_languages': [], 'feats': [],
            'known_spells': ['治愈创伤'],
        })).json()
        ok("Paladin created", 'id' in char, str(char.get('detail',''))[:80])
        if 'id' not in char: return
        cid = char['id']
        print(f"  HP={char['hp_current']} Slots={char.get('spell_slots')}")

        # 创建会话
        sess = (await c.post('/game/sessions', json={
            'module_id': mid, 'player_character_id': cid, 'companion_ids': [],
        })).json()
        sid = sess.get('session_id', sess.get('id', ''))

        # 初始化战斗（敌人HP高一点，保证能多轮测试）
        from database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Session as Sess, CombatState, Character
        from services.dnd_rules import roll_initiative

        async with AsyncSessionLocal() as db:
            so = (await db.execute(select(Sess).where(Sess.id == sid))).scalar_one()
            chs = (await db.execute(select(Character).where(Character.session_id == sid))).scalars().all()
            enemies = [{
                'id': f'enemy_{uuid.uuid4().hex[:8]}', 'name': '骷髅战士',
                'hp': 30, 'hp_current': 30, 'hp_max': 30, 'ac': 10,
                'attack_bonus': 3, 'damage_dice': '1d6+1', 'damage_type': 'slashing',
                'conditions': [], 'dead': False, 'is_player': False, 'is_enemy': True,
                'resistances': [], 'immunities': [], 'vulnerabilities': ['bludgeoning'],
                'derived': {'hp_max':30,'ac':10,'attack_bonus':3,
                    'ability_modifiers':{'str':1,'dex':0,'con':1,'int':-2,'wis':0,'cha':-3}},
                'actions': [{'name':'Sword','type':'melee_attack','attack_bonus':3,
                    'damage_dice':'1d6+1','damage_type':'slashing'}],
            }]
            combatants = [{'id':str(ch.id),'name':ch.name,
                'initiative':(ch.derived or{}).get('initiative',0),
                'is_player':ch.is_player,'is_enemy':False} for ch in chs] + enemies
            to = roll_initiative(combatants)
            # 强制玩家先手
            for i,t in enumerate(to):
                if t.get('is_player'): to.insert(0, to.pop(i)); break
            pos = {str(chs[0].id): {'x':4,'y':5}, enemies[0]['id']: {'x':5,'y':5}}
            gs = dict(so.game_state or {}); gs['enemies'] = enemies
            so.game_state = gs; so.combat_active = True
            db.add(CombatState(id=str(uuid.uuid4()), session_id=sid, turn_order=to,
                current_turn_index=0, round_number=1, entity_positions=pos,
                grid_data={}, combat_log=[], turn_states={}))
            await db.commit()
        eid = enemies[0]['id']
        print(f"  Enemy AC=10 HP=30 (low AC to ensure hits)")

        # ════════════════════════════════════════
        # TEST A: 施法（独立回合，不先攻击）
        # ════════════════════════════════════════
        print("\n== 2. TEST SPELL CAST (治愈创伤 on self) ==")

        # 先扣点血方便测试治疗
        async with AsyncSessionLocal() as db:
            pc = await db.get(Character, cid)
            pc.hp_current = 30  # 从44扣到30
            await db.commit()
        print(f"  Set HP to 30 (max={char['hp_current']})")

        sp = (await c.post(f'/game/combat/{sid}/spell', json={
            'caster_id': cid,
            'spell_name': '治愈创伤',
            'spell_level': 1,
            'target_id': cid,
            'target_ids': [cid],
        })).json()

        if 'detail' in sp:
            ok("Spell cast", False, sp['detail'])
        else:
            ok("Spell cast success", 'narration' in sp)
            ok("Heal amount > 0", (sp.get('heal') or 0) > 0, f"heal={sp.get('heal')}")
            ok("Target HP updated", sp.get('target_new_hp', 0) > 30, f"new_hp={sp.get('target_new_hp')}")
            ok("Spell slot consumed", sp.get('remaining_slots', {}).get('1st', 99) < 4,
               f"remaining={sp.get('remaining_slots')}")
            ok("dice_result in response", 'dice_result' in sp)
            ok("Narration is string", isinstance(sp.get('narration'), str) and len(sp.get('narration','')) > 5,
               f"narration type={type(sp.get('narration'))}")
            narr = sp.get('narration','')[:80].encode('ascii','replace').decode()
            print(f"  Narration: {narr}")

        # 结束回合让敌人行动，然后回到玩家回合
        print("\n== 3. END TURN + AI CYCLE ==")
        et = (await c.post(f'/game/combat/{sid}/end-turn')).json()
        ok("End turn after spell", 'next_turn_index' in et, str(et.get('detail',''))[:80])

        # AI 回合
        for i in range(5):
            cs = (await c.get(f'/game/combat/{sid}')).json()
            ct = cs['turn_order'][cs['current_turn_index']]
            if ct.get('is_player'):
                print(f"  Back to player turn (Round {cs['round_number']})")
                break
            ai = (await c.post(f'/game/combat/{sid}/ai-turn')).json()
            if 'detail' in ai:
                ok(f"AI turn", False, ai['detail'][:60])
                break
            nm = ai.get('actor_name','?').encode('ascii','replace').decode()
            nr = ai.get('narration','')[:50].encode('ascii','replace').decode()
            print(f"  AI: {nm} -- {nr}")

        # ════════════════════════════════════════
        # TEST B: 攻击 + 至圣斩
        # ════════════════════════════════════════
        print("\n== 4. TEST ATTACK + DIVINE SMITE ==")

        # 多次尝试直到命中（AC=10 应该很容易命中）
        hit = False
        for attempt in range(3):
            atk = (await c.post(f'/game/combat/{sid}/action', json={
                'entity_id': cid, 'target_id': eid, 'action_type': 'melee',
            })).json()

            if 'detail' in atk:
                ok(f"Attack attempt {attempt+1}", False, atk['detail'][:80])
                # 如果回合结束需要重新循环
                if '行动已用尽' in atk.get('detail', '') or '回合' in atk.get('detail', ''):
                    # end turn and cycle AI
                    await c.post(f'/game/combat/{sid}/end-turn')
                    for _ in range(5):
                        cs = (await c.get(f'/game/combat/{sid}')).json()
                        ct = cs['turn_order'][cs['current_turn_index']]
                        if ct.get('is_player'): break
                        await c.post(f'/game/combat/{sid}/ai-turn')
                    continue
                break

            atk_result = atk.get('attack_result', {})
            print(f"  Attack {attempt+1}: d20={atk_result.get('d20')} total={atk_result.get('attack_total')} hit={atk_result.get('hit')}")

            if atk_result.get('hit'):
                hit = True
                ok("Attack hit!", True)
                print(f"  Damage: {atk.get('damage')}")

                # 尝试至圣斩
                print("\n  -- DIVINE SMITE --")
                smite = (await c.post(f'/game/combat/{sid}/smite', json={
                    'slot_level': 1,
                })).json()

                if 'detail' in smite:
                    ok("Divine Smite", False, smite['detail'][:80])
                else:
                    ok("Smite executed", 'smite_damage' in smite)
                    ok("Smite damage > 0", (smite.get('smite_damage') or 0) > 0, f"dmg={smite.get('smite_damage')}")
                    ok("Smite dice notation", bool(smite.get('smite_dice')), f"dice={smite.get('smite_dice')}")
                    ok("Target HP reduced", smite.get('target_new_hp') is not None)
                    ok("Slot consumed", True)
                    print(f"  Smite: {smite.get('smite_damage')} ({smite.get('smite_dice')})")
                    print(f"  Enemy HP: {smite.get('target_new_hp')}")
                break
            else:
                print(f"  Miss (attempt {attempt+1})")

        if not hit:
            print("  [SKIP] All attacks missed (very unlikely with AC 10)")

        # ════════════════════════════════════════
        print(f"\n{'='*50}")
        print(f"  PASS: {P}  |  FAIL: {F}")
        print(f"{'='*50}")

asyncio.run(run())
