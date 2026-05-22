"""Browser-level multiplayer Combat smoke test via Chrome DevTools Protocol.

The script creates a disposable module, host, guest, room, and two claimed
characters. It then seeds a deterministic CombatState directly in the local
SQLite database, opens two isolated browser contexts, and clicks the real
Combat UI:

- host controls are enabled on host turn
- guest controls are disabled on host turn
- host clicks End Turn
- guest controls become enabled through websocket refresh
- guest toggles move mode and clicks a battlefield cell

Example:
    python scripts/multiplayer_combat_browser_smoke.py --cdp http://127.0.0.1:9222
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

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


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def seed_combat_state(db_path: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Make the generated multiplayer room enter a deterministic combat."""
    session_id = data["session_id"]
    host_char_id = data["host_character"]["id"]
    guest_char_id = data["guest_character"]["id"]
    enemy_id = f"combat-goblin-{data['stamp']}"

    enemy = {
        "id": enemy_id,
        "name": "Combat Goblin",
        "hp_current": 30,
        "max_hp": 30,
        "conditions": [],
        "derived": {
            "hp_max": 30,
            "ac": 10,
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
                0,
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


async def prepare_combat_data(base_api: str, db_path: Path) -> dict[str, Any]:
    stamp = uuid.uuid4().hex[:6]
    module_id = create_module(db_path)
    async with httpx.AsyncClient(base_url=base_api, timeout=60, trust_env=False) as client:
        host = await api_request(
            client,
            "POST",
            "/auth/register",
            json={"username": f"combat_host_{stamp}", "password": "password", "display_name": f"combat_host_{stamp}"},
        )
        guest = await api_request(
            client,
            "POST",
            "/auth/register",
            json={"username": f"combat_guest_{stamp}", "password": "password", "display_name": f"combat_guest_{stamp}"},
        )
        room = await api_request(
            client,
            "POST",
            "/game/rooms/create",
            token=host["token"],
            json={"module_id": module_id, "save_name": f"Combat Browser {stamp}", "max_players": 2},
        )
        await api_request(client, "POST", "/game/rooms/join", token=guest["token"], json={"room_code": room["room_code"]})

        host_payload = character_payload(module_id, f"HostBlade{stamp}")
        guest_payload = character_payload(module_id, f"GuestBlade{stamp}")
        host_char = await api_request(client, "POST", "/characters/create", json=host_payload)
        guest_char = await api_request(client, "POST", "/characters/create", json=guest_payload)
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
    data["combat_seed"] = seed_combat_state(db_path, data)
    return data


async def run_browser_flow(args: argparse.Namespace, data: dict[str, Any]) -> dict[str, Any]:
    base_api = args.base_api.rstrip("/")
    base_web = args.base_web.rstrip("/")
    session_id = data["session_id"]
    artifact_dir = Path(args.artifacts)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    version = httpx.get(f"{args.cdp.rstrip('/')}/json/version", timeout=5, trust_env=False).json()
    async with websockets.connect(version["webSocketDebuggerUrl"], open_timeout=10) as ws:
        cdp = CDP(ws)
        await cdp.start()

        async def make_page(label: str, user: dict[str, Any]) -> dict[str, Any]:
            ctx = (await cdp.call("Target.createBrowserContext"))["browserContextId"]
            target = (await cdp.call("Target.createTarget", {"url": "about:blank", "browserContextId": ctx}))["targetId"]
            sid = (await cdp.call("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]
            await cdp.call("Page.enable", session_id=sid)
            await cdp.call("Runtime.enable", session_id=sid)
            await cdp.call("Log.enable", session_id=sid)
            await cdp.call(
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
            await cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": bootstrap}, session_id=sid)
            await cdp.call("Page.navigate", {"url": f"{base_web}/combat/{session_id}"}, session_id=sid)
            return {"label": label, "ctx": ctx, "target": target, "sid": sid, "user": user}

        async def eval_page(page: dict[str, Any], expression: str) -> Any:
            result = await cdp.call(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
                session_id=page["sid"],
            )
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")

        async def page_probe(page: dict[str, Any]) -> dict[str, Any]:
            return await eval_page(
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
                    unitIds: [...document.querySelectorAll('[data-testid^="combat-unit-"]')]
                        .map(el => el.getAttribute('data-testid')),
                    currentLabel: document.body.innerText.match(/当前回合[^\\n]*/)?.[0] || '',
                    errors: [...document.querySelectorAll('.error, [role="alert"]')].map(el => el.innerText),
                }))()
                """,
            )

        async def visible_testid(
            page: dict[str, Any],
            testid: str,
            *,
            require_enabled: bool = True,
        ) -> dict[str, Any] | None:
            return await eval_page(
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

        async def click_testid(page: dict[str, Any], testid: str, *, timeout: float = 15.0) -> dict[str, Any]:
            await cdp.call("Target.activateTarget", {"targetId": page["target"]})
            await cdp.call("Page.bringToFront", session_id=page["sid"])
            await asyncio.sleep(0.15)
            rect = await wait_for(
                lambda: visible_testid(page, testid, require_enabled=True),
                timeout=timeout,
                interval=0.25,
                label=f"{page['label']} {testid}",
            )
            for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
                params = {"type": event_type, "x": rect["x"], "y": rect["y"]}
                if event_type != "mouseMoved":
                    params.update({"button": "left", "clickCount": 1})
                await cdp.call("Input.dispatchMouseEvent", params, session_id=page["sid"])
            return rect

        async def dom_click_testid(page: dict[str, Any], testid: str) -> bool:
            return bool(await eval_page(
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

        async def screenshot(page: dict[str, Any], name: str) -> str:
            path = artifact_dir / f"{name}.png"
            png = (await cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, session_id=page["sid"]))["data"]
            path.write_bytes(base64.b64decode(png))
            return str(path.resolve())

        host_page = await make_page("host", data["host"])
        guest_page = await make_page("guest", data["guest"])
        pages = [host_page, guest_page]

        async def both_combat_loaded() -> list[dict[str, Any]] | None:
            probes = [await page_probe(page) for page in pages]
            host_unit = f"combat-unit-{data['host_character']['id']}"
            guest_unit = f"combat-unit-{data['guest_character']['id']}"
            ok = all(
                f"/combat/{session_id}" in probe["url"]
                and probe["endTurn"]
                and host_unit in probe["unitIds"]
                and guest_unit in probe["unitIds"]
                for probe in probes
            )
            return probes if ok else None

        initial_probes = await wait_for(both_combat_loaded, timeout=35, interval=0.5, label="both combat pages loaded")

        async def ws_two() -> dict[str, Any] | None:
            ready = await get_ready(base_api)
            count = ready.get("ws", {}).get("room_connections", {}).get(session_id, 0)
            return ready if count >= 2 else None

        ready_before = await wait_for(ws_two, timeout=20, interval=0.5, label="combat ws connections >= 2")

        host_initial = await page_probe(host_page)
        guest_initial = await page_probe(guest_page)
        if not host_initial["endTurn"] or host_initial["endTurn"]["disabled"]:
            raise RuntimeError(f"host end turn should be enabled: {host_initial}")
        if not guest_initial["endTurn"] or not guest_initial["endTurn"]["disabled"]:
            raise RuntimeError(f"guest end turn should be disabled on host turn: {guest_initial}")

        initial_host_screenshot = await screenshot(host_page, f"multiplayer-combat-{session_id[:8]}-host-turn")
        initial_guest_screenshot = await screenshot(guest_page, f"multiplayer-combat-{session_id[:8]}-guest-waiting")

        async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
            guest_bad_end = await client.post(
                f"/game/combat/{session_id}/end-turn",
                headers={"Authorization": f"Bearer {data['guest']['token']}"},
            )
            guest_bad_move = await client.post(
                f"/game/combat/{session_id}/move",
                headers={"Authorization": f"Bearer {data['guest']['token']}"},
                json={"entity_id": data["host_character"]["id"], "to_x": 5, "to_y": 6},
            )

        async def guest_turn_enabled() -> dict[str, Any] | None:
            probe = await page_probe(guest_page)
            end_turn = probe.get("endTurn")
            move_toggle = probe.get("moveToggle")
            if end_turn and not end_turn["disabled"] and move_toggle and not move_toggle["disabled"]:
                return probe
            return None

        await click_testid(host_page, "combat-end-turn")
        try:
            guest_enabled_probe = await wait_for(
                guest_turn_enabled,
                timeout=8,
                interval=0.5,
                label="guest controls enabled after host end-turn",
            )
        except TimeoutError:
            await dom_click_testid(host_page, "combat-end-turn")
            guest_enabled_probe = await wait_for(
                guest_turn_enabled,
                timeout=20,
                interval=0.5,
                label="guest controls enabled after host end-turn DOM fallback",
            )

        async def host_waiting_after_end() -> dict[str, Any] | None:
            probe = await page_probe(host_page)
            end_turn = probe.get("endTurn")
            return probe if end_turn and end_turn["disabled"] else None

        host_after_end_probe = await wait_for(host_waiting_after_end, timeout=20, interval=0.5, label="host controls disabled after turn passes")

        guest_turn_screenshot = await screenshot(guest_page, f"multiplayer-combat-{session_id[:8]}-guest-turn")

        await click_testid(guest_page, "combat-move-toggle")
        async def guest_move_mode_on() -> dict[str, Any] | None:
            probe = await page_probe(guest_page)
            move_toggle = probe.get("moveToggle")
            if move_toggle and not move_toggle["disabled"] and "\u2713" in move_toggle["text"]:
                return probe
            return None

        try:
            guest_move_mode_probe = await wait_for(
                guest_move_mode_on,
                timeout=4,
                interval=0.25,
                label="guest move mode enabled",
            )
        except TimeoutError:
            await dom_click_testid(guest_page, "combat-move-toggle")
            guest_move_mode_probe = await wait_for(
                guest_move_mode_on,
                timeout=10,
                interval=0.25,
                label="guest move mode enabled DOM fallback",
            )

        await click_testid(guest_page, "combat-cell-8-5")

        async def guest_moved() -> dict[str, Any] | None:
            async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
                combat = await api_request(client, "GET", f"/game/combat/{session_id}", token=data["guest"]["token"])
            pos = combat.get("entity_positions", {}).get(data["guest_character"]["id"])
            return combat if pos == {"x": 8, "y": 5} else None

        try:
            combat_after_move = await wait_for(guest_moved, timeout=8, interval=0.5, label="guest moved to 8,5")
        except TimeoutError:
            await dom_click_testid(guest_page, "combat-cell-8-5")
            combat_after_move = await wait_for(guest_moved, timeout=20, interval=0.5, label="guest moved to 8,5 DOM fallback")
        guest_moved_screenshot = await screenshot(guest_page, f"multiplayer-combat-{session_id[:8]}-guest-moved")
        ready_after = await get_ready(base_api)

        output = {
            "session_id": session_id,
            "room_code": data["room_code"],
            "host_user_id": data["host"]["user_id"],
            "guest_user_id": data["guest"]["user_id"],
            "host_character_id": data["host_character"]["id"],
            "guest_character_id": data["guest_character"]["id"],
            "enemy_id": data["combat_seed"]["enemy_id"],
            "initial_probes": initial_probes,
            "host_after_end_probe": host_after_end_probe,
            "guest_enabled_probe": guest_enabled_probe,
            "guest_move_mode_probe": guest_move_mode_probe,
            "api_permission_checks": {
                "guest_end_turn_on_host_turn": guest_bad_end.status_code,
                "guest_move_host_on_host_turn": guest_bad_move.status_code,
                "guest_end_turn_body": guest_bad_end.text[:300],
                "guest_move_host_body": guest_bad_move.text[:300],
            },
            "combat_after_move": {
                "current_turn_index": combat_after_move.get("current_turn_index"),
                "round_number": combat_after_move.get("round_number"),
                "guest_position": combat_after_move.get("entity_positions", {}).get(data["guest_character"]["id"]),
                "turn_states": combat_after_move.get("turn_states", {}),
            },
            "ready_before_ws": ready_before.get("ws"),
            "ready_after_ws": ready_after.get("ws"),
            "screenshots": {
                "host_turn": initial_host_screenshot,
                "guest_waiting": initial_guest_screenshot,
                "guest_turn": guest_turn_screenshot,
                "guest_moved": guest_moved_screenshot,
            },
            "browser_events": [
                event for event in cdp.events
                if event.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded")
            ],
        }

        for page in pages:
            try:
                await cdp.call("Target.closeTarget", {"targetId": page["target"]})
                await cdp.call("Target.disposeBrowserContext", {"browserContextId": page["ctx"]})
            except Exception:
                pass

        if guest_bad_end.status_code != 403 or guest_bad_move.status_code != 403:
            raise RuntimeError(f"expected permission checks to be 403: {output['api_permission_checks']}")
        return output


async def main_async(args: argparse.Namespace) -> int:
    data = await prepare_combat_data(args.base_api.rstrip("/"), Path(args.db_path))
    output = await run_browser_flow(args, data)
    print(json.dumps(output, ensure_ascii=True, indent=2))
    room_connections = output["ready_after_ws"]["room_connections"].get(output["session_id"], 0)
    if room_connections < 2:
        return 1
    if output["combat_after_move"]["guest_position"] != {"x": 8, "y": 5}:
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a two-user CDP browser Combat smoke test.")
    parser.add_argument("--base-api", default="http://127.0.0.1:8002")
    parser.add_argument("--base-web", default="http://127.0.0.1:3000")
    parser.add_argument("--cdp", default="http://127.0.0.1:9222")
    parser.add_argument("--db-path", default="backend/ai_trpg.db")
    parser.add_argument("--artifacts", default="doc/test-artifacts")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
