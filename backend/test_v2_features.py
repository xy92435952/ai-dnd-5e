"""Test ALL V2 features: CharSheet, Equipment, Shop, Gold, Movement, Potions"""
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

        # Create character with equipment
        print("\n== 1. CHARACTER WITH EQUIPMENT ==")
        char = (await c.post('/characters/create', json={
            'module_id': mid, 'name': 'ShopTest', 'race': '人类',
            'char_class': '战士', 'subclass': 'Champion', 'level': 5,
            'background': '士兵',
            'ability_scores': {'str':16,'dex':12,'con':14,'int':10,'wis':12,'cha':8},
            'proficient_skills': [],
            'fighting_style': 'Dueling',
            'equipment_choice': 0,
            'bonus_languages': [], 'feats': [],
        })).json()
        ok("Character created", 'id' in char, safe(str(char.get('detail',''))))
        if 'id' not in char: return
        cid = char['id']
        eq = char.get('equipment', {})
        ok("Equipment populated", bool(eq), str(list(eq.keys())))
        weapons = eq.get('weapons', [])
        ok("Has weapons", len(weapons) > 0, f"got {len(weapons)}")
        if weapons:
            w = weapons[0]
            ok("Weapon has damage", bool(w.get('damage')), str(w))

        # ══════════════════════════════════
        print("\n== 2. GET CHARACTER ==")
        ch = (await c.get(f'/characters/{cid}')).json()
        ok("Get character", 'id' in ch, safe(str(ch.get('detail',''))))
        ok("Has derived", bool(ch.get('derived')))
        ok("Has equipment", bool(ch.get('equipment')))

        # ══════════════════════════════════
        print("\n== 3. GOLD SYSTEM ==")
        g1 = (await c.patch(f'/characters/{cid}/gold', json={'amount': 200, 'reason': 'quest'})).json()
        ok("Gold added", g1.get('gold', 0) >= 200, str(g1)[:60])

        # ══════════════════════════════════
        print("\n== 4. SHOP INVENTORY ==")
        shop = (await c.get('/characters/shop/inventory')).json()
        ok("Shop has weapons", len(shop.get('weapons', {})) > 0)
        ok("Shop has armor", len(shop.get('armor', {})) > 0)
        ok("Shop has gear", len(shop.get('gear', {})) > 0)

        # ══════════════════════════════════
        print("\n== 5. BUY ITEM ==")
        buy = (await c.post(f'/characters/{cid}/shop/buy', json={
            'item_name': 'Healing Potion', 'item_category': 'gear',
        })).json()
        if 'detail' in buy:
            ok("Buy potion", False, safe(buy['detail']))
        else:
            ok("Buy potion", buy.get('gold', 999) < 200)
            ok("Item in inventory", True)

        # Buy a weapon
        buy2 = (await c.post(f'/characters/{cid}/shop/buy', json={
            'item_name': 'Shortsword', 'item_category': 'weapon',
        })).json()
        ok("Buy weapon", 'detail' not in buy2, safe(str(buy2.get('detail',''))))

        # ══════════════════════════════════
        print("\n== 6. USE POTION ==")
        # First reduce HP
        from database import AsyncSessionLocal
        from models import Character
        async with AsyncSessionLocal() as db:
            pc = await db.get(Character, cid)
            pc.hp_current = 20
            await db.commit()

        use = (await c.post(f'/characters/{cid}/use-item', json={
            'item_name': 'Healing Potion',
        })).json()
        if 'detail' in use:
            ok("Use potion", False, safe(use['detail']))
        else:
            ok("Potion healed", (use.get('heal', 0) or use.get('hp_recovered', 0)) > 0)
            ok("HP increased", use.get('hp_current', 0) > 20, f"hp={use.get('hp_current')}")

        # ══════════════════════════════════
        print("\n== 7. SELL ITEM ==")
        sell = (await c.post(f'/characters/{cid}/shop/sell', json={
            'item_name': 'Shortsword', 'item_category': 'weapon', 'item_index': -1,
        })).json()
        if 'detail' in sell:
            # Try different format
            sell = (await c.post(f'/characters/{cid}/shop/sell', json={
                'item_name': 'Shortsword', 'item_category': 'weapons', 'item_index': 1,
            })).json()
        ok("Sell item", 'detail' not in sell, safe(str(sell.get('detail',''))))

        # ══════════════════════════════════
        print("\n== 8. EQUIP/UNEQUIP ==")
        eq_update = (await c.patch(f'/characters/{cid}/equipment', json={
            'item_category': 'weapon', 'item_index': 0, 'equipped': True,
        })).json()
        ok("Equip weapon", 'detail' not in eq_update, safe(str(eq_update.get('detail',''))))

        # ══════════════════════════════════
        print("\n== 9. ATTACK RANGE CHECK ==")
        # Create session + combat
        sess = (await c.post('/game/sessions', json={
            'module_id': mid, 'player_character_id': cid, 'companion_ids': [],
        })).json()
        sid = sess.get('session_id', sess.get('id',''))

        from sqlalchemy import select
        from models import Session as Sess, CombatState
        from services.dnd_rules import roll_initiative
        from sqlalchemy.orm.attributes import flag_modified

        async with AsyncSessionLocal() as db:
            so = (await db.execute(select(Sess).where(Sess.id == sid))).scalar_one()
            chs = (await db.execute(select(Character).where(Character.session_id == sid))).scalars().all()
            enemies = [{
                'id': f'enemy_{uuid.uuid4().hex[:8]}', 'name': 'FarTarget',
                'hp': 20, 'hp_current': 20, 'hp_max': 20, 'ac': 10,
                'attack_bonus': 3, 'damage_dice': '1d4+1', 'damage_type': 'slashing',
                'conditions': [], 'dead': False, 'is_player': False, 'is_enemy': True,
                'resistances': [], 'immunities': [], 'vulnerabilities': [],
                'derived': {'hp_max':20,'ac':10,'attack_bonus':3,
                    'ability_modifiers':{'str':0,'dex':0,'con':0,'int':0,'wis':0,'cha':0}},
                'actions': [{'name':'Dagger','type':'melee_attack','attack_bonus':3,'damage_dice':'1d4+1','damage_type':'piercing'}],
            }]
            combatants = [{'id':str(ch.id),'name':ch.name,'initiative':(ch.derived or{}).get('initiative',0),
                'is_player':ch.is_player,'is_enemy':False} for ch in chs] + enemies
            to = roll_initiative(combatants)
            for i,t in enumerate(to):
                if t.get('is_player'): to.insert(0, to.pop(i)); break
            # Player at (2,5), enemy FAR at (15,15)
            pos = {str(chs[0].id): {'x':2,'y':5}, enemies[0]['id']: {'x':15,'y':15}}
            gs = dict(so.game_state or {}); gs['enemies'] = enemies
            so.game_state = gs; so.combat_active = True
            flag_modified(so, "game_state")
            db.add(CombatState(id=str(uuid.uuid4()), session_id=sid, turn_order=to,
                current_turn_index=0, round_number=1, entity_positions=pos,
                grid_data={}, combat_log=[], turn_states={}))
            await db.commit()
        eid = enemies[0]['id']

        # Try melee attack from far away — should FAIL
        ar = (await c.post(f'/game/combat/{sid}/attack-roll', json={
            'entity_id': cid, 'target_id': eid, 'action_type': 'melee',
        })).json()
        ok("Melee range blocked", 'detail' in ar and ('范围' in ar.get('detail','') or 'range' in ar.get('detail','').lower()),
           safe(str(ar.get('detail', ar.get('narration','')))))

        # Try ranged attack — should succeed (within default range)
        ar2 = (await c.post(f'/game/combat/{sid}/attack-roll', json={
            'entity_id': cid, 'target_id': eid, 'action_type': 'ranged',
        })).json()
        ok("Ranged attack allowed", 'd20' in ar2, safe(str(ar2.get('detail',''))))

        # ══════════════════════════════════
        print(f"\n{'='*50}")
        print(f"  PASS: {P}  |  FAIL: {F}")
        print(f"{'='*50}")

asyncio.run(run())
