"""Extended multiplayer Combat browser smoke tests with per-scenario cleanup.

Each scenario creates disposable multiplayer data, opens two isolated Chrome
CDP browser contexts, drives the real Combat UI, closes the contexts, and waits
for the tested session's websocket count to return to zero before continuing.

Example:
    python scripts/multiplayer_combat_extended_browser_smoke.py --auto-chrome
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import sqlite3
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import websockets

from multiplayer_deep_browser_smoke import (
    CDP,
    api_request,
    character_payload,
    create_module,
    get_ready,
    wait_for,
)


class ChromeHandle:
    def __init__(self, proc: subprocess.Popen | None = None, user_data_dir: Path | None = None):
        self.proc = proc
        self.user_data_dir = user_data_dir

    async def close(self) -> None:
        if not self.proc:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if self.user_data_dir:
            shutil.rmtree(self.user_data_dir, ignore_errors=True)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _character_derived(conn: sqlite3.Connection, character_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT derived FROM characters WHERE id = ?", (character_id,)).fetchone()
    return json.loads(row["derived"] or "{}") if row else {}


def _grant_reaction_spells(conn: sqlite3.Connection, character_id: str, spells: list[str]) -> dict[str, Any]:
    derived = _character_derived(conn, character_id)
    slots = dict(derived.get("spell_slots_max") or {})
    slots["1st"] = max(1, int(slots.get("1st", 0) or 0))
    derived["spell_slots_max"] = slots
    conn.execute(
        """
        UPDATE characters
        SET known_spells = ?, prepared_spells = ?, spell_slots = ?, derived = ?
        WHERE id = ?
        """,
        (
            json.dumps(spells, ensure_ascii=False),
            json.dumps(spells, ensure_ascii=False),
            json.dumps(slots, ensure_ascii=False),
            json.dumps(derived, ensure_ascii=False),
            character_id,
        ),
    )
    return derived


def _chrome_candidates() -> list[str]:
    return [
        "chrome.exe",
        "chrome",
        "msedge.exe",
        "msedge",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]


async def ensure_cdp(args: argparse.Namespace) -> ChromeHandle:
    cdp = args.cdp.rstrip("/")
    try:
        httpx.get(f"{cdp}/json/version", timeout=2, trust_env=False).raise_for_status()
        return ChromeHandle()
    except Exception:
        if not args.auto_chrome:
            raise RuntimeError(f"CDP is not available at {cdp}; pass --auto-chrome to launch a temporary browser")

    browser_path = next((candidate for candidate in _chrome_candidates() if shutil.which(candidate) or Path(candidate).exists()), None)
    if not browser_path:
        raise RuntimeError("Could not find Chrome or Edge for --auto-chrome")
    resolved = shutil.which(browser_path) or browser_path
    user_data_dir = Path(tempfile.mkdtemp(prefix="ai-dnd-cdp-"))
    proc = subprocess.Popen(
        [
            resolved,
            "--remote-debugging-port=9222",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            httpx.get(f"{cdp}/json/version", timeout=2, trust_env=False).raise_for_status()
            return ChromeHandle(proc, user_data_dir)
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(0.4)
    await ChromeHandle(proc, user_data_dir).close()
    raise RuntimeError(f"Chrome CDP did not become ready: {last_error}")


def seed_combat_state(
    db_path: Path,
    data: dict[str, Any],
    *,
    enemy_hp: int = 30,
    enemy_ac: int = 8,
    current_turn_index: int = 0,
    enemy_attack_bonus: int = 4,
    enemy_damage_die: int = 6,
    host_reaction_spells: list[str] | None = None,
    guest_reaction_spells: list[str] | None = None,
    host_pending_ai_attack: bool = False,
    guest_pending_ai_attack: bool = False,
) -> dict[str, Any]:
    session_id = data["session_id"]
    host_char_id = data["host_character"]["id"]
    guest_char_id = data["guest_character"]["id"]
    enemy_id = f"combat-goblin-{data['stamp']}"
    enemy = {
        "id": enemy_id,
        "name": "Combat Goblin",
        "hp_current": enemy_hp,
        "max_hp": enemy_hp,
        "conditions": [],
        "derived": {
            "hp_max": enemy_hp,
            "ac": enemy_ac,
            "attack_bonus": enemy_attack_bonus,
            "hit_die": enemy_damage_die,
            "ability_modifiers": {"str": 0, "dex": 1, "con": 0, "wis": 0},
        },
        "actions": [{
            "name": "Scimitar",
            "type": "melee_attack",
            "damage_dice": "1d6",
            "attack_bonus": 4,
        }],
        "speed": 30,
        "tactics": "test target",
    }
    positions = {
        host_char_id: {"x": 5, "y": 5},
        enemy_id: {"x": 6, "y": 5},
        guest_char_id: {"x": 7, "y": 5},
    }
    turn_order = [
        {
            "character_id": host_char_id,
            "name": data["host_character"]["name"],
            "initiative": 18,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": guest_char_id,
            "name": data["guest_character"]["name"],
            "initiative": 15,
            "is_player": True,
            "is_enemy": False,
        },
        {
            "character_id": enemy_id,
            "name": enemy["name"],
            "initiative": 10,
            "is_player": False,
            "is_enemy": True,
        },
    ]
    turn_states = {
        host_char_id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "attacks_made": 0,
            "attacks_max": 1,
        },
        guest_char_id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "attacks_made": 0,
            "attacks_max": 1,
        },
        enemy_id: {
            "action_used": False,
            "bonus_action_used": False,
            "reaction_used": False,
            "movement_used": 0,
            "movement_max": 6,
            "attacks_made": 0,
            "attacks_max": 1,
        },
    }

    combat_id = str(uuid.uuid4())
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT game_state FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise RuntimeError(f"session not found: {session_id}")
        game_state = json.loads(row["game_state"] or "{}")
        game_state["enemies"] = [enemy]
        game_state.setdefault("multiplayer", {})["current_speaker_user_id"] = data["host"]["user_id"]
        conn.execute(
            "UPDATE sessions SET combat_active = 1, game_state = ? WHERE id = ?",
            (json.dumps(game_state, ensure_ascii=False), session_id),
        )
        conn.execute("DELETE FROM combat_states WHERE session_id = ?", (session_id,))
        host_derived = (
            _grant_reaction_spells(conn, host_char_id, host_reaction_spells)
            if host_reaction_spells
            else _character_derived(conn, host_char_id)
        )
        guest_derived = _grant_reaction_spells(conn, guest_char_id, guest_reaction_spells) if guest_reaction_spells else _character_derived(conn, guest_char_id)
        if host_pending_ai_attack:
            host_ac = int((host_derived or {}).get("ac") or 10)
            attack_total = host_ac + 2
            turn_states[host_char_id]["pending_ai_attack"] = {
                "pending_attack_id": f"seeded-host-pending-{data['stamp']}",
                "actor_id": enemy_id,
                "actor_name": enemy["name"],
                "target_id": host_char_id,
                "target_name": data["host_character"]["name"],
                "attack_roll": {
                    "d20": 12,
                    "attack_bonus": max(0, attack_total - 12),
                    "attack_total": attack_total,
                    "target_ac": host_ac,
                    "hit": True,
                    "is_crit": False,
                    "is_fumble": False,
                },
                "damage": 1,
                "raw_damage": 1,
                "damage_type": "slashing",
                "next_turn_index": 0,
                "entity_positions": positions,
                "available_reactions": [{
                    "id": "shield",
                    "name": "Shield",
                    "type": "spell",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": 1,
                    "effect": "+5 AC until the start of your next turn",
                    "resulting_ac": host_ac + 5,
                }],
                "options": [{
                    "type": "shield",
                    "label": "Shield",
                    "target_id": enemy_id,
                    "cost": "1st-level spell slot",
                    "effect": "+5 AC until the start of your next turn",
                }],
            }
        if guest_pending_ai_attack:
            guest_ac = int((guest_derived or {}).get("ac") or 10)
            attack_total = guest_ac + 2
            turn_states[guest_char_id]["pending_ai_attack"] = {
                "pending_attack_id": f"seeded-guest-pending-{data['stamp']}",
                "actor_id": enemy_id,
                "actor_name": enemy["name"],
                "target_id": guest_char_id,
                "target_name": data["guest_character"]["name"],
                "attack_roll": {
                    "d20": 12,
                    "attack_bonus": max(0, attack_total - 12),
                    "attack_total": attack_total,
                    "target_ac": guest_ac,
                    "hit": True,
                    "is_crit": False,
                    "is_fumble": False,
                },
                "damage": 1,
                "raw_damage": 1,
                "damage_type": "slashing",
                "next_turn_index": 0,
                "entity_positions": positions,
                "available_reactions": [{
                    "id": "shield",
                    "name": "Shield",
                    "type": "spell",
                    "cost": "1st-level spell slot",
                    "slot_level": "1st",
                    "slots_remaining": 1,
                    "effect": "+5 AC until the start of your next turn",
                    "resulting_ac": guest_ac + 5,
                }],
                "options": [{
                    "type": "shield",
                    "label": "Shield",
                    "target_id": enemy_id,
                    "cost": "1st-level spell slot",
                    "effect": "+5 AC until the start of your next turn",
                }],
            }
        conn.execute(
            """
            INSERT INTO combat_states (
                id, session_id, grid_data, entity_positions, turn_order,
                current_turn_index, round_number, combat_log, turn_states
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                combat_id,
                session_id,
                json.dumps({}, ensure_ascii=False),
                json.dumps(positions, ensure_ascii=False),
                json.dumps(turn_order, ensure_ascii=False),
                current_turn_index,
                1,
                json.dumps([], ensure_ascii=False),
                json.dumps(turn_states, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "combat_id": combat_id,
        "enemy_id": enemy_id,
        "positions": positions,
        "turn_order": turn_order,
    }


def enemy_from_combat(combat: dict[str, Any], enemy_id: str) -> dict[str, Any] | None:
    entities = combat.get("entities") or {}
    if enemy_id in entities:
        return entities[enemy_id]
    return next((e for e in combat.get("enemies", []) if e.get("id") == enemy_id), None)


async def prepare_combat_data(
    base_api: str,
    db_path: Path,
    *,
    enemy_hp: int = 30,
    enemy_ac: int = 8,
    current_turn_index: int = 0,
    enemy_attack_bonus: int = 4,
    enemy_damage_die: int = 6,
    host_reaction_spells: list[str] | None = None,
    guest_reaction_spells: list[str] | None = None,
    host_pending_ai_attack: bool = False,
    guest_pending_ai_attack: bool = False,
) -> dict[str, Any]:
    stamp = uuid.uuid4().hex[:6]
    module_id = create_module(db_path)
    async with httpx.AsyncClient(base_url=base_api, timeout=60, trust_env=False) as client:
        host = await api_request(
            client,
            "POST",
            "/auth/register",
            json={"username": f"cx_host_{stamp}", "password": "password", "display_name": f"cx_host_{stamp}"},
        )
        guest = await api_request(
            client,
            "POST",
            "/auth/register",
            json={"username": f"cx_guest_{stamp}", "password": "password", "display_name": f"cx_guest_{stamp}"},
        )
        room = await api_request(
            client,
            "POST",
            "/game/rooms/create",
            token=host["token"],
            json={"module_id": module_id, "save_name": f"Combat Extended {stamp}", "max_players": 2},
        )
        await api_request(client, "POST", "/game/rooms/join", token=guest["token"], json={"room_code": room["room_code"]})
        host_char = await api_request(client, "POST", "/characters/create", json=character_payload(module_id, f"HostBlade{stamp}"))
        guest_char = await api_request(client, "POST", "/characters/create", json=character_payload(module_id, f"GuestBlade{stamp}"))
        await api_request(
            client,
            "POST",
            f"/game/rooms/{room['session_id']}/claim-character",
            token=host["token"],
            json={"character_id": host_char["id"]},
        )
        await api_request(
            client,
            "POST",
            f"/game/rooms/{room['session_id']}/claim-character",
            token=guest["token"],
            json={"character_id": guest_char["id"]},
        )
        await api_request(client, "POST", f"/game/rooms/{room['session_id']}/start", token=host["token"])

    data = {
        "stamp": stamp,
        "module_id": module_id,
        "session_id": room["session_id"],
        "room_code": room["room_code"],
        "host": host,
        "guest": guest,
        "host_character": host_char,
        "guest_character": guest_char,
    }
    data["combat_seed"] = seed_combat_state(
        db_path,
        data,
        enemy_hp=enemy_hp,
        enemy_ac=enemy_ac,
        current_turn_index=current_turn_index,
        enemy_attack_bonus=enemy_attack_bonus,
        enemy_damage_die=enemy_damage_die,
        host_reaction_spells=host_reaction_spells,
        guest_reaction_spells=guest_reaction_spells,
        host_pending_ai_attack=host_pending_ai_attack,
        guest_pending_ai_attack=guest_pending_ai_attack,
    )
    return data


class BrowserHarness:
    def __init__(self, args: argparse.Namespace, data: dict[str, Any], cdp: CDP):
        self.args = args
        self.data = data
        self.cdp = cdp
        self.base_api = args.base_api.rstrip("/")
        self.base_web = args.base_web.rstrip("/")
        self.session_id = data["session_id"]
        self.artifact_dir = Path(args.artifacts)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.pages: list[dict[str, Any]] = []

    async def make_page(self, label: str, user: dict[str, Any], *, dice_queue: list[Any] | None = None) -> dict[str, Any]:
        ctx = (await self.cdp.call("Target.createBrowserContext"))["browserContextId"]
        target = (await self.cdp.call("Target.createTarget", {"url": "about:blank", "browserContextId": ctx}))["targetId"]
        sid = (await self.cdp.call("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]
        await self.cdp.call("Page.enable", session_id=sid)
        await self.cdp.call("Runtime.enable", session_id=sid)
        await self.cdp.call("Log.enable", session_id=sid)
        await self.cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1365, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            session_id=sid,
        )
        user_payload = {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user["display_name"],
        }
        bootstrap = (
            f"localStorage.setItem('token', {json.dumps(user['token'])});"
            f"localStorage.setItem('user', {json.dumps(json.dumps(user_payload))});"
        )
        if dice_queue is not None:
            bootstrap += f"localStorage.setItem('__ai_dnd_test_dice_queue', {json.dumps(json.dumps(dice_queue))});"
        await self.cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": bootstrap}, session_id=sid)
        await self.cdp.call("Page.navigate", {"url": f"{self.base_web}/combat/{self.session_id}"}, session_id=sid)
        page = {"label": label, "ctx": ctx, "target": target, "sid": sid, "user": user}
        self.pages.append(page)
        return page

    async def eval_page(self, page: dict[str, Any], expression: str) -> Any:
        result = await self.cdp.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            session_id=page["sid"],
        )
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    async def page_probe(self, page: dict[str, Any]) -> dict[str, Any]:
        return await self.eval_page(
            page,
            """
            (() => ({
                url: location.href,
                text: document.body.innerText,
                endTurn: (() => {
                    const el = document.querySelector('[data-testid="combat-end-turn"]');
                    return el ? { disabled: !!el.disabled, text: el.innerText } : null;
                })(),
                moveToggle: (() => {
                    const el = document.querySelector('[data-testid="combat-move-toggle"]');
                    return el ? { disabled: !!el.disabled, text: el.innerText } : null;
                })(),
                attackSkill: (() => {
                    const el = document.querySelector('[data-testid="combat-skill-atk"]');
                    return el ? { text: el.innerText, classes: el.className } : null;
                })(),
                reactionPrompt: (() => {
                    const el = document.querySelector('[data-testid="combat-reaction-prompt"]');
                    return el ? { text: el.innerText } : null;
                })(),
                reactionButtons: [...document.querySelectorAll('[data-testid^="combat-reaction-"]')]
                    .map(el => ({ id: el.getAttribute('data-testid'), disabled: !!el.disabled, text: el.innerText })),
                unitIds: [...document.querySelectorAll('[data-testid^="combat-unit-"]')]
                    .map(el => el.getAttribute('data-testid')),
                errors: [...document.querySelectorAll('.error, [role="alert"]')].map(el => el.innerText),
            }))()
            """,
        )

    async def visible_testid(self, page: dict[str, Any], testid: str, *, require_enabled: bool = True) -> dict[str, Any] | None:
        return await self.eval_page(
            page,
            f"""
            (() => {{
                const el = document.querySelector('[data-testid="{testid}"]');
                if (!el) return null;
                if ({str(require_enabled).lower()} && el.disabled) return null;
                const r = el.getBoundingClientRect();
                if (!r.width || !r.height) return null;
                const vw = window.innerWidth || document.documentElement.clientWidth || 1365;
                const vh = window.innerHeight || document.documentElement.clientHeight || 900;
                const left = Math.max(0, r.left);
                const right = Math.min(vw, r.right);
                const top = Math.max(0, r.top);
                const bottom = Math.min(vh, r.bottom);
                if (right <= left || bottom <= top) return null;
                return {{
                    x: Math.min(Math.max((left + right) / 2, 4), vw - 4),
                    y: Math.min(Math.max((top + bottom) / 2, 4), vh - 4),
                    disabled: !!el.disabled,
                    text: el.innerText || el.value || '',
                }};
            }})()
            """,
        )

    async def click_testid(self, page: dict[str, Any], testid: str, *, timeout: float = 15.0) -> dict[str, Any]:
        await self.cdp.call("Target.activateTarget", {"targetId": page["target"]})
        await self.cdp.call("Page.bringToFront", session_id=page["sid"])
        await asyncio.sleep(0.15)
        rect = await wait_for(
            lambda: self.visible_testid(page, testid, require_enabled=True),
            timeout=timeout,
            interval=0.25,
            label=f"{page['label']} {testid}",
        )
        for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
            params = {"type": event_type, "x": rect["x"], "y": rect["y"]}
            if event_type != "mouseMoved":
                params.update({"button": "left", "clickCount": 1})
            await self.cdp.call("Input.dispatchMouseEvent", params, session_id=page["sid"])
        return rect

    async def dom_click_testid(self, page: dict[str, Any], testid: str) -> bool:
        return bool(await self.eval_page(
            page,
            f"""
            (() => {{
                const el = document.querySelector('[data-testid="{testid}"]');
                if (!el || el.disabled) return false;
                el.click();
                return true;
            }})()
            """,
        ))

    async def click_then_wait(
        self,
        page: dict[str, Any],
        testid: str,
        condition: Callable[[], Awaitable[Any]],
        *,
        label: str,
        first_timeout: float = 6.0,
        second_timeout: float = 20.0,
        interval: float = 0.5,
    ) -> Any:
        await self.click_testid(page, testid)
        try:
            return await wait_for(condition, timeout=first_timeout, interval=interval, label=label)
        except TimeoutError:
            await self.dom_click_testid(page, testid)
            return await wait_for(condition, timeout=second_timeout, interval=interval, label=f"{label} DOM fallback")

    async def screenshot(self, page: dict[str, Any], name: str) -> str:
        path = self.artifact_dir / f"{name}.png"
        png = (await self.cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, session_id=page["sid"]))["data"]
        path.write_bytes(base64.b64decode(png))
        return str(path.resolve())

    async def wait_loaded(self) -> list[dict[str, Any]]:
        host_unit = f"combat-unit-{self.data['host_character']['id']}"
        guest_unit = f"combat-unit-{self.data['guest_character']['id']}"

        async def both_combat_loaded() -> list[dict[str, Any]] | None:
            probes = [await self.page_probe(page) for page in self.pages]
            ok = all(
                f"/combat/{self.session_id}" in probe["url"]
                and probe["endTurn"]
                and host_unit in probe["unitIds"]
                and guest_unit in probe["unitIds"]
                for probe in probes
            )
            return probes if ok else None

        return await wait_for(both_combat_loaded, timeout=35, interval=0.5, label="both combat pages loaded")

    async def wait_ws(self, expected: int) -> dict[str, Any]:
        async def condition() -> dict[str, Any] | None:
            ready = await get_ready(self.base_api)
            count = ready.get("ws", {}).get("room_connections", {}).get(self.session_id, 0)
            return ready if count == expected else None

        return await wait_for(condition, timeout=20, interval=0.5, label=f"ws count {expected} for {self.session_id}")

    async def cleanup(self) -> None:
        for page in self.pages:
            try:
                await self.cdp.call("Target.closeTarget", {"targetId": page["target"]})
            except Exception:
                pass
            try:
                await self.cdp.call("Target.disposeBrowserContext", {"browserContextId": page["ctx"]})
            except Exception:
                pass
        self.pages.clear()
        try:
            await self.wait_ws(0)
        except Exception:
            pass
        try:
            async with httpx.AsyncClient(base_url=self.base_api, timeout=15, trust_env=False) as client:
                await client.post(
                    f"/game/combat/{self.session_id}/end",
                    headers={"Authorization": f"Bearer {self.data['host']['token']}"},
                )
        except Exception:
            pass


async def combat_state(base_api: str, session_id: str, token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
        return await api_request(client, "GET", f"/game/combat/{session_id}", token=token)


async def scenario_turn_move(args: argparse.Namespace, cdp: CDP) -> dict[str, Any]:
    data = await prepare_combat_data(args.base_api.rstrip("/"), Path(args.db_path), enemy_hp=30, enemy_ac=8)
    harness = BrowserHarness(args, data, cdp)
    try:
        host_page = await harness.make_page("host", data["host"])
        guest_page = await harness.make_page("guest", data["guest"])
        initial_probes = await harness.wait_loaded()
        ready_before = await harness.wait_ws(2)
        host_initial = await harness.page_probe(host_page)
        guest_initial = await harness.page_probe(guest_page)
        if not host_initial["endTurn"] or host_initial["endTurn"]["disabled"]:
            raise RuntimeError("host end turn should be enabled")
        if not guest_initial["endTurn"] or not guest_initial["endTurn"]["disabled"]:
            raise RuntimeError("guest end turn should be disabled on host turn")

        async with httpx.AsyncClient(base_url=args.base_api.rstrip("/"), timeout=30, trust_env=False) as client:
            guest_bad_end = await client.post(
                f"/game/combat/{data['session_id']}/end-turn",
                headers={"Authorization": f"Bearer {data['guest']['token']}"},
            )
            guest_bad_move = await client.post(
                f"/game/combat/{data['session_id']}/move",
                headers={"Authorization": f"Bearer {data['guest']['token']}"},
                json={"entity_id": data["host_character"]["id"], "to_x": 5, "to_y": 6},
            )

        async def guest_turn_enabled() -> dict[str, Any] | None:
            probe = await harness.page_probe(guest_page)
            end_turn = probe.get("endTurn")
            move_toggle = probe.get("moveToggle")
            return probe if end_turn and not end_turn["disabled"] and move_toggle and not move_toggle["disabled"] else None

        async def guest_move_mode_on() -> dict[str, Any] | None:
            probe = await harness.page_probe(guest_page)
            move_toggle = probe.get("moveToggle")
            return probe if move_toggle and not move_toggle["disabled"] and "\u2713" in move_toggle["text"] else None

        async def moved() -> dict[str, Any] | None:
            combat = await combat_state(args.base_api.rstrip("/"), data["session_id"], data["guest"]["token"])
            pos = combat.get("entity_positions", {}).get(data["guest_character"]["id"])
            return combat if pos == {"x": 8, "y": 5} else None

        await harness.screenshot(host_page, f"multiplayer-combat-{data['session_id'][:8]}-turn-move-host")
        guest_enabled_probe = await harness.click_then_wait(
            host_page,
            "combat-end-turn",
            guest_turn_enabled,
            label="guest controls enabled",
        )
        await harness.click_then_wait(
            guest_page,
            "combat-move-toggle",
            guest_move_mode_on,
            label="guest move mode enabled",
            first_timeout=4,
            second_timeout=10,
            interval=0.25,
        )
        combat_after_move = await harness.click_then_wait(
            guest_page,
            "combat-cell-8-5",
            moved,
            label="guest moved",
            first_timeout=8,
            second_timeout=20,
        )
        moved_shot = await harness.screenshot(guest_page, f"multiplayer-combat-{data['session_id'][:8]}-turn-move-guest-moved")
        return {
            "scenario": "turn_move",
            "session_id": data["session_id"],
            "room_code": data["room_code"],
            "initial_probes": initial_probes,
            "ready_before_ws": ready_before.get("ws"),
            "guest_enabled_probe": guest_enabled_probe,
            "api_permission_checks": {
                "guest_end_turn_on_host_turn": guest_bad_end.status_code,
                "guest_move_host_on_host_turn": guest_bad_move.status_code,
            },
            "guest_position": combat_after_move.get("entity_positions", {}).get(data["guest_character"]["id"]),
            "screenshots": {"guest_moved": moved_shot},
        }
    finally:
        await harness.cleanup()


async def scenario_attack_damage(args: argparse.Namespace, cdp: CDP) -> dict[str, Any]:
    data = await prepare_combat_data(args.base_api.rstrip("/"), Path(args.db_path), enemy_hp=30, enemy_ac=5)
    harness = BrowserHarness(args, data, cdp)
    try:
        host_page = await harness.make_page(
            "host",
            data["host"],
            dice_queue=[{"total": 18, "rolls": [18]}, {"total": 6, "rolls": [6]}],
        )
        guest_page = await harness.make_page("guest", data["guest"])
        await harness.wait_loaded()
        ready_before = await harness.wait_ws(2)
        enemy_id = data["combat_seed"]["enemy_id"]
        async def target_selected() -> dict[str, Any] | None:
            return await harness.eval_page(
                host_page,
                """
                (() => {
                    const text = document.body.innerText;
                    const skill = document.querySelector('[data-testid="combat-skill-atk"]');
                    return text.includes('TARGET') && skill ? { text, skillText: skill.innerText } : null;
                })()
                """,
            )

        async with httpx.AsyncClient(base_url=args.base_api.rstrip("/"), timeout=30, trust_env=False) as client:
            guest_bad_attack = await client.post(
                f"/game/combat/{data['session_id']}/attack-roll",
                headers={"Authorization": f"Bearer {data['guest']['token']}"},
                json={
                    "entity_id": data["host_character"]["id"],
                    "target_id": enemy_id,
                    "action_type": "melee",
                    "d20_value": 18,
                },
            )

        async def enemy_damaged() -> dict[str, Any] | None:
            combat = await combat_state(args.base_api.rstrip("/"), data["session_id"], data["host"]["token"])
            enemy = enemy_from_combat(combat, enemy_id)
            if enemy and enemy.get("hp_current", 30) < 30:
                return combat
            return None

        await harness.click_then_wait(
            host_page,
            f"combat-unit-{enemy_id}",
            target_selected,
            label="enemy target selected",
            first_timeout=4,
            second_timeout=10,
            interval=0.25,
        )
        combat_after_attack = await harness.click_then_wait(
            host_page,
            "combat-skill-atk",
            enemy_damaged,
            label="enemy damaged by host attack",
            first_timeout=12,
            second_timeout=30,
        )
        shot = await harness.screenshot(host_page, f"multiplayer-combat-{data['session_id'][:8]}-attack-damage")
        enemy = enemy_from_combat(combat_after_attack, enemy_id) or {}
        turn_state = combat_after_attack.get("turn_states", {}).get(data["host_character"]["id"], {})
        return {
            "scenario": "attack_damage",
            "session_id": data["session_id"],
            "room_code": data["room_code"],
            "ready_before_ws": ready_before.get("ws"),
            "enemy_id": enemy_id,
            "enemy_hp_after": enemy.get("hp_current"),
            "host_turn_state": turn_state,
            "api_permission_checks": {
                "guest_attack_as_host": guest_bad_attack.status_code,
                "guest_attack_body": guest_bad_attack.text[:240],
            },
            "screenshots": {"attack_damage": shot},
        }
    finally:
        await harness.cleanup()


async def scenario_ai_turn_cycle(args: argparse.Namespace, cdp: CDP) -> dict[str, Any]:
    data = await prepare_combat_data(args.base_api.rstrip("/"), Path(args.db_path), enemy_hp=30, enemy_ac=8)
    harness = BrowserHarness(args, data, cdp)
    try:
        host_page = await harness.make_page("host", data["host"])
        guest_page = await harness.make_page("guest", data["guest"])
        await harness.wait_loaded()
        ready_before = await harness.wait_ws(2)

        async def guest_turn_enabled() -> dict[str, Any] | None:
            probe = await harness.page_probe(guest_page)
            end_turn = probe.get("endTurn")
            return probe if end_turn and not end_turn["disabled"] else None

        async def round_two_host_turn() -> dict[str, Any] | None:
            combat = await combat_state(args.base_api.rstrip("/"), data["session_id"], data["host"]["token"])
            if combat.get("current_turn_index") == 0 and combat.get("round_number") == 2:
                return combat
            return None

        async def host_controls_enabled() -> dict[str, Any] | None:
            probe = await harness.page_probe(host_page)
            end_turn = probe.get("endTurn")
            return probe if end_turn and not end_turn["disabled"] else None

        await harness.click_then_wait(
            host_page,
            "combat-end-turn",
            guest_turn_enabled,
            label="guest turn enabled before AI cycle",
        )
        combat_after_ai = await harness.click_then_wait(
            guest_page,
            "combat-end-turn",
            round_two_host_turn,
            label="enemy AI advances round back to host",
            first_timeout=18,
            second_timeout=45,
            interval=0.75,
        )
        host_enabled_probe = await wait_for(
            host_controls_enabled,
            timeout=15,
            interval=0.5,
            label="host controls enabled after AI cycle",
        )
        if "undefined" in host_enabled_probe.get("text", ""):
            raise RuntimeError("AI turn combat log rendered an undefined value")
        shot = await harness.screenshot(host_page, f"multiplayer-combat-{data['session_id'][:8]}-ai-turn-cycle")
        return {
            "scenario": "ai_turn_cycle",
            "session_id": data["session_id"],
            "room_code": data["room_code"],
            "ready_before_ws": ready_before.get("ws"),
            "round_number": combat_after_ai.get("round_number"),
            "current_turn_index": combat_after_ai.get("current_turn_index"),
            "current_turn_character_id": (
                combat_after_ai.get("turn_order", [{}])[combat_after_ai.get("current_turn_index", 0)]
                .get("character_id")
            ),
            "expected_host_character_id": data["host_character"]["id"],
            "host_controls_enabled_probe": host_enabled_probe,
            "screenshots": {"ai_turn_cycle": shot},
        }
    finally:
        await harness.cleanup()


async def _run_reaction_prompt_attempt(
    args: argparse.Namespace,
    cdp: CDP,
    *,
    attempt: int,
) -> dict[str, Any]:
    data = await prepare_combat_data(
        args.base_api.rstrip("/"),
        Path(args.db_path),
        enemy_hp=30,
        enemy_ac=8,
        current_turn_index=2,
        enemy_attack_bonus=99,
        enemy_damage_die=1,
        host_reaction_spells=["Shield"],
        host_pending_ai_attack=True,
    )
    harness = BrowserHarness(args, data, cdp)
    try:
        host_page = await harness.make_page("host", data["host"])
        guest_page = await harness.make_page("guest", data["guest"])
        await harness.wait_loaded()
        ready_before = await harness.wait_ws(2)

        async def shield_prompt_visible() -> dict[str, Any] | None:
            host_probe = await harness.page_probe(host_page)
            guest_probe = await harness.page_probe(guest_page)
            buttons = host_probe.get("reactionButtons") or []
            guest_buttons = guest_probe.get("reactionButtons") or []
            has_shield = any(
                button.get("id") == "combat-reaction-shield" and not button.get("disabled")
                for button in buttons
            )
            guest_has_prompt = bool(guest_probe.get("reactionPrompt")) or any(
                button.get("id") == "combat-reaction-shield"
                for button in guest_buttons
            )
            if host_probe.get("reactionPrompt") and has_shield and not guest_has_prompt:
                return {"host": host_probe, "guest": guest_probe}
            return None

        async def shield_resolved() -> dict[str, Any] | None:
            combat = await combat_state(args.base_api.rstrip("/"), data["session_id"], data["host"]["token"])
            turn_state = combat.get("turn_states", {}).get(data["host_character"]["id"], {})
            host_entity = (combat.get("entities") or {}).get(data["host_character"]["id"], {})
            pending_attack = turn_state.get("pending_ai_attack")
            if (
                not pending_attack
                and "shield_spell" in (host_entity.get("conditions") or [])
                and combat.get("current_turn_index") == 0
                and combat.get("round_number") == 2
            ):
                return combat
            return None

        prompt_probe = await wait_for(
            shield_prompt_visible,
            timeout=25,
            interval=0.5,
            label="host shield reaction prompt",
        )
        prompt_shot = await harness.screenshot(host_page, f"multiplayer-combat-{data['session_id'][:8]}-reaction-prompt")
        combat_after_reaction = await harness.click_then_wait(
            host_page,
            "combat-reaction-shield",
            shield_resolved,
            label="shield reaction resolved",
            first_timeout=12,
            second_timeout=30,
            interval=0.5,
        )
        resolved_shot = await harness.screenshot(host_page, f"multiplayer-combat-{data['session_id'][:8]}-reaction-resolved")

        host_entity = (combat_after_reaction.get("entities") or {}).get(data["host_character"]["id"], {})
        return {
            "scenario": "reaction_prompt",
            "attempt": attempt,
            "session_id": data["session_id"],
            "room_code": data["room_code"],
            "ready_before_ws": ready_before.get("ws"),
            "prompt_probe": {
                "reactionPrompt": prompt_probe["host"].get("reactionPrompt"),
                "reactionButtons": prompt_probe["host"].get("reactionButtons"),
                "guestReactionPrompt": prompt_probe["guest"].get("reactionPrompt"),
                "guestReactionButtons": prompt_probe["guest"].get("reactionButtons"),
            },
            "host_turn_state": combat_after_reaction.get("turn_states", {}).get(data["host_character"]["id"], {}),
            "host_conditions": host_entity.get("conditions") or [],
            "host_hp_after_reaction": host_entity.get("hp_current"),
            "round_number": combat_after_reaction.get("round_number"),
            "current_turn_index": combat_after_reaction.get("current_turn_index"),
            "screenshots": {
                "reaction_prompt": prompt_shot,
                "reaction_resolved": resolved_shot,
            },
        }
    finally:
        await harness.cleanup()


async def scenario_reaction_prompt(args: argparse.Namespace, cdp: CDP) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            result = await _run_reaction_prompt_attempt(args, cdp, attempt=attempt)
            result["attempts"] = attempts + [
                {
                    "attempt": attempt,
                    "session_id": result["session_id"],
                    "status": "passed",
                }
            ]
            return result
        except TimeoutError as exc:
            ready = await get_ready(args.base_api.rstrip("/"))
            attempts.append({
                "attempt": attempt,
                "status": "retry",
                "reason": str(exc),
                "ready_after_cleanup": ready.get("ws"),
            })
            if attempt == max_attempts:
                raise
    raise RuntimeError("reaction prompt retry loop exited unexpectedly")


async def scenario_guest_reaction_prompt(args: argparse.Namespace, cdp: CDP) -> dict[str, Any]:
    data = await prepare_combat_data(
        args.base_api.rstrip("/"),
        Path(args.db_path),
        enemy_hp=30,
        enemy_ac=8,
        current_turn_index=2,
        guest_reaction_spells=["Shield"],
        guest_pending_ai_attack=True,
    )
    harness = BrowserHarness(args, data, cdp)
    try:
        host_page = await harness.make_page("host", data["host"])
        guest_page = await harness.make_page("guest", data["guest"])
        await harness.wait_loaded()
        ready_before = await harness.wait_ws(2)

        async def guest_shield_prompt_visible() -> dict[str, Any] | None:
            guest_probe = await harness.page_probe(guest_page)
            host_probe = await harness.page_probe(host_page)
            guest_buttons = guest_probe.get("reactionButtons") or []
            host_buttons = host_probe.get("reactionButtons") or []
            guest_has_shield = any(
                button.get("id") == "combat-reaction-shield" and not button.get("disabled")
                for button in guest_buttons
            )
            host_has_prompt = bool(host_probe.get("reactionPrompt")) or any(
                button.get("id") == "combat-reaction-shield"
                for button in host_buttons
            )
            if guest_probe.get("reactionPrompt") and guest_has_shield and not host_has_prompt:
                return {"guest": guest_probe, "host": host_probe}
            return None

        async def guest_shield_resolved() -> dict[str, Any] | None:
            combat = await combat_state(args.base_api.rstrip("/"), data["session_id"], data["guest"]["token"])
            guest_turn_state = combat.get("turn_states", {}).get(data["guest_character"]["id"], {})
            host_turn_state = combat.get("turn_states", {}).get(data["host_character"]["id"], {})
            guest_entity = (combat.get("entities") or {}).get(data["guest_character"]["id"], {})
            pending_attack = guest_turn_state.get("pending_ai_attack")
            if (
                not pending_attack
                and not host_turn_state.get("pending_ai_attack")
                and "shield_spell" in (guest_entity.get("conditions") or [])
                and combat.get("current_turn_index") == 0
                and combat.get("round_number") == 2
            ):
                return combat
            return None

        prompt_probe = await wait_for(
            guest_shield_prompt_visible,
            timeout=25,
            interval=0.5,
            label="guest shield reaction prompt",
        )
        prompt_shot = await harness.screenshot(guest_page, f"multiplayer-combat-{data['session_id'][:8]}-guest-reaction-prompt")
        host_no_prompt_shot = await harness.screenshot(host_page, f"multiplayer-combat-{data['session_id'][:8]}-guest-reaction-host-no-prompt")
        combat_after_reaction = await harness.click_then_wait(
            guest_page,
            "combat-reaction-shield",
            guest_shield_resolved,
            label="guest shield reaction resolved",
            first_timeout=12,
            second_timeout=30,
            interval=0.5,
        )
        resolved_shot = await harness.screenshot(guest_page, f"multiplayer-combat-{data['session_id'][:8]}-guest-reaction-resolved")

        guest_entity = (combat_after_reaction.get("entities") or {}).get(data["guest_character"]["id"], {})
        return {
            "scenario": "guest_reaction_prompt",
            "session_id": data["session_id"],
            "room_code": data["room_code"],
            "ready_before_ws": ready_before.get("ws"),
            "prompt_probe": {
                "guestReactionPrompt": prompt_probe["guest"].get("reactionPrompt"),
                "guestReactionButtons": prompt_probe["guest"].get("reactionButtons"),
                "hostReactionPrompt": prompt_probe["host"].get("reactionPrompt"),
                "hostReactionButtons": prompt_probe["host"].get("reactionButtons"),
            },
            "guest_turn_state": combat_after_reaction.get("turn_states", {}).get(data["guest_character"]["id"], {}),
            "host_turn_state": combat_after_reaction.get("turn_states", {}).get(data["host_character"]["id"], {}),
            "guest_conditions": guest_entity.get("conditions") or [],
            "guest_hp_after_reaction": guest_entity.get("hp_current"),
            "round_number": combat_after_reaction.get("round_number"),
            "current_turn_index": combat_after_reaction.get("current_turn_index"),
            "screenshots": {
                "guest_reaction_prompt": prompt_shot,
                "host_no_prompt": host_no_prompt_shot,
                "guest_reaction_resolved": resolved_shot,
            },
        }
    finally:
        await harness.cleanup()


async def run_scenario(
    args: argparse.Namespace,
    cdp: CDP,
    fn: Callable[[argparse.Namespace, CDP], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    result = await fn(args, cdp)
    await asyncio.sleep(0.5)
    ready = await get_ready(args.base_api.rstrip("/"))
    result["ready_after_cleanup"] = ready.get("ws")
    return result


async def main_async(args: argparse.Namespace) -> int:
    chrome = await ensure_cdp(args)
    results: list[dict[str, Any]] = []
    try:
        version = httpx.get(f"{args.cdp.rstrip('/')}/json/version", timeout=5, trust_env=False).json()
        async with websockets.connect(version["webSocketDebuggerUrl"], open_timeout=10) as ws:
            cdp = CDP(ws)
            await cdp.start()
            scenarios = [
                ("turn_move", scenario_turn_move),
                ("attack_damage", scenario_attack_damage),
                ("ai_turn_cycle", scenario_ai_turn_cycle),
                ("reaction_prompt", scenario_reaction_prompt),
                ("guest_reaction_prompt", scenario_guest_reaction_prompt),
            ]
            selected = [
                scenario
                for name, scenario in scenarios
                if not args.scenario or name in args.scenario
            ][: args.max_scenarios]
            for scenario in selected:
                results.append(await run_scenario(args, cdp, scenario))
            for result in results:
                result["browser_events"] = [
                    event for event in cdp.events
                    if event.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded")
                    and result.get("session_id", "") in json.dumps(event, ensure_ascii=False)
                ]
    finally:
        await chrome.close()

    print(json.dumps({"results": results}, ensure_ascii=True, indent=2))
    for result in results:
        scenario = result.get("scenario")
        cleanup_ws = result.get("ready_after_cleanup", {})
        if (
            cleanup_ws.get("rooms") != 0
            or cleanup_ws.get("connections") != 0
            or cleanup_ws.get("users") != 0
            or cleanup_ws.get("room_connections")
        ):
            return 1
        if scenario == "turn_move":
            checks = result.get("api_permission_checks", {})
            if checks.get("guest_end_turn_on_host_turn") != 403 or checks.get("guest_move_host_on_host_turn") != 403:
                return 1
            if result.get("guest_position") != {"x": 8, "y": 5}:
                return 1
        if scenario == "attack_damage":
            checks = result.get("api_permission_checks", {})
            if checks.get("guest_attack_as_host") != 403:
                return 1
            if not isinstance(result.get("enemy_hp_after"), int) or result["enemy_hp_after"] >= 30:
                return 1
            if result.get("host_turn_state", {}).get("attacks_made") != 1:
                return 1
        if scenario == "ai_turn_cycle":
            if result.get("round_number") != 2 or result.get("current_turn_index") != 0:
                return 1
            if result.get("current_turn_character_id") != result.get("expected_host_character_id"):
                return 1
        if scenario == "reaction_prompt":
            if "shield_spell" not in (result.get("host_conditions") or []):
                return 1
            if result.get("host_turn_state", {}).get("pending_ai_attack"):
                return 1
            if result.get("round_number") != 2 or result.get("current_turn_index") != 0:
                return 1
        if scenario == "guest_reaction_prompt":
            if "shield_spell" not in (result.get("guest_conditions") or []):
                return 1
            if result.get("guest_turn_state", {}).get("pending_ai_attack"):
                return 1
            if result.get("host_turn_state", {}).get("pending_ai_attack"):
                return 1
            prompt_probe = result.get("prompt_probe", {})
            if prompt_probe.get("hostReactionPrompt"):
                return 1
            if result.get("round_number") != 2 or result.get("current_turn_index") != 0:
                return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run extended two-user CDP browser Combat smoke tests.")
    parser.add_argument("--base-api", default="http://127.0.0.1:8002")
    parser.add_argument("--base-web", default="http://127.0.0.1:3000")
    parser.add_argument("--cdp", default="http://127.0.0.1:9222")
    parser.add_argument("--db-path", default="backend/ai_trpg.db")
    parser.add_argument("--artifacts", default="doc/test-artifacts")
    parser.add_argument("--auto-chrome", action="store_true", help="Launch a temporary Chrome/Edge CDP instance if --cdp is not reachable.")
    parser.add_argument("--max-scenarios", type=int, default=5)
    parser.add_argument("--scenario", action="append", choices=[
        "turn_move",
        "attack_damage",
        "ai_turn_cycle",
        "reaction_prompt",
        "guest_reaction_prompt",
    ])
    return parser.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
