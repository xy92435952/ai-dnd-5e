"""Browser-level multiplayer smoke test via Chrome DevTools Protocol.

The script creates a disposable module, host, guest, room, and two claimed
characters, then opens two isolated Chrome browser contexts through an existing
CDP endpoint. It clicks the real room "start adventure" button in the host
page and verifies both pages navigate to Adventure with two websocket
connections still present. It then drives real Adventure UI controls for one
host action, one guest group intent, and a multiplayer rest vote.

Example:
    python scripts/multiplayer_deep_browser_smoke.py --cdp http://127.0.0.1:9222
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


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.next_id = 1
        self.pending: dict[int, asyncio.Future] = {}
        self.events: list[dict[str, Any]] = []
        self.reader_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.reader_task = asyncio.create_task(self._reader())

    async def _reader(self) -> None:
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg:
                fut = self.pending.pop(msg["id"], None)
                if fut and not fut.done():
                    fut.set_result(msg)
            else:
                self.events.append(msg)

    async def call(self, method: str, params: dict[str, Any] | None = None, session_id: str | None = None) -> dict[str, Any]:
        msg_id = self.next_id
        self.next_id += 1
        payload: dict[str, Any] = {"id": msg_id, "method": method}
        if params is not None:
            payload["params"] = params
        if session_id is not None:
            payload["sessionId"] = session_id
        fut = asyncio.get_running_loop().create_future()
        self.pending[msg_id] = fut
        await self.ws.send(json.dumps(payload))
        res = await asyncio.wait_for(fut, timeout=20)
        if "error" in res:
            raise RuntimeError(f"{method} failed: {res['error']}")
        return res.get("result", {})


def create_module(db_path: Path) -> str:
    module_id = str(uuid.uuid4())
    parsed = {
        "setting": "Deep multiplayer smoke tavern",
        "tone": "heroic fantasy",
        "plot_summary": "A two-player smoke adventure starts in a lantern-lit tavern.",
        "scenes": [{
            "title": "Lantern Inn",
            "description": "The party stands at the Lantern Inn threshold while rain taps against the shutters.",
        }],
        "npcs": [],
        "monsters": [],
        "magic_items": [],
        "level_min": 1,
        "level_max": 3,
        "recommended_party_size": 2,
    }
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO modules (
                id, user_id, name, file_path, file_type, parsed_content,
                level_min, level_max, recommended_party_size, parse_status, parse_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                module_id,
                None,
                f"DeepBrowser-{module_id[:6]}",
                "",
                "md",
                json.dumps(parsed, ensure_ascii=False),
                1,
                3,
                2,
                "done",
                None,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return module_id


async def api_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    token: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = await client.request(method, path, headers=headers, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} {response.status_code} {response.text}")
    return response.json()


def character_payload(module_id: str, name: str) -> dict[str, Any]:
    return {
        "module_id": module_id,
        "name": name,
        "race": "Human",
        "char_class": "Fighter",
        "level": 1,
        "background": "Soldier",
        "alignment": "Neutral Good",
        "ability_scores": {"str": 16, "dex": 14, "con": 15, "int": 10, "wis": 12, "cha": 8},
        "proficient_skills": ["\u8fd0\u52a8", "\u611f\u77e5"],
        "known_spells": [],
        "cantrips": [],
        "equipment_choice": 1,
        "personality": "brave smoke-test adventurer",
    }


async def prepare_data(base_api: str, db_path: Path) -> dict[str, Any]:
    stamp = uuid.uuid4().hex[:6]
    module_id = create_module(db_path)
    async with httpx.AsyncClient(base_url=base_api, timeout=60, trust_env=False) as client:
        host = await api_request(
            client,
            "POST",
            "/auth/register",
            json={"username": f"deep_host_{stamp}", "password": "password", "display_name": f"deep_host_{stamp}"},
        )
        guest = await api_request(
            client,
            "POST",
            "/auth/register",
            json={"username": f"deep_guest_{stamp}", "password": "password", "display_name": f"deep_guest_{stamp}"},
        )
        room = await api_request(
            client,
            "POST",
            "/game/rooms/create",
            token=host["token"],
            json={"module_id": module_id, "save_name": f"Deep Browser {stamp}", "max_players": 2},
        )
        await api_request(client, "POST", "/game/rooms/join", token=guest["token"], json={"room_code": room["room_code"]})
        host_char = await api_request(client, "POST", "/characters/create", json=character_payload(module_id, f"HostHero{stamp}"))
        guest_char = await api_request(client, "POST", "/characters/create", json=character_payload(module_id, f"GuestHero{stamp}"))
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
        room_info = await api_request(client, "GET", f"/game/rooms/{room['session_id']}", token=host["token"])

    return {
        "stamp": stamp,
        "module_id": module_id,
        "session_id": room["session_id"],
        "room_code": room["room_code"],
        "host": host,
        "guest": guest,
        "host_character": host_char,
        "guest_character": guest_char,
        "room_info": room_info,
    }


async def wait_for(condition, timeout: float, interval: float, label: str):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = await condition()
        if last:
            return last
        await asyncio.sleep(interval)
    raise TimeoutError(f"timed out waiting for {label}; last={last!r}")


async def get_ready(base_api: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        return (await client.get(f"{base_api}/ready")).json()


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
            await cdp.call("Page.navigate", {"url": f"{base_web}/room/{session_id}"}, session_id=sid)
            return {"label": label, "ctx": ctx, "target": target, "sid": sid, "user": user}

        host_page = await make_page("host", data["host"])
        guest_page = await make_page("guest", data["guest"])
        pages = [host_page, guest_page]

        async def eval_page(page: dict[str, Any], expression: str):
            result = await cdp.call(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
                session_id=page["sid"],
            )
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")

        async def page_state(page: dict[str, Any]) -> dict[str, Any]:
            return await eval_page(
                page,
                """
                (() => ({
                    url: location.href,
                    title: document.title,
                    text: document.body.innerText,
                    buttons: [...document.querySelectorAll('button')].map((b, i) => ({
                        i, text: b.innerText, disabled: b.disabled, className: String(b.className)
                    })),
                    testids: [...document.querySelectorAll('[data-testid]')].map((el, i) => ({
                        i, testid: el.getAttribute('data-testid'), text: el.innerText || el.value || '', disabled: !!el.disabled
                    }))
                }))()
                """,
            )

        async def click_testid(page: dict[str, Any], testid: str, *, timeout: float = 15.0) -> dict[str, Any]:
            async def find_rect():
                return await eval_page(
                    page,
                    f"""
                    (() => {{
                        const el = document.querySelector('[data-testid="{testid}"]');
                        if (!el || el.disabled) return null;
                        const r = el.getBoundingClientRect();
                        if (!r.width || !r.height) return null;
                        const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1365;
                        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 900;
                        const visibleLeft = Math.max(0, r.left);
                        const visibleRight = Math.min(viewportWidth, r.right);
                        const visibleTop = Math.max(0, r.top);
                        const visibleBottom = Math.min(viewportHeight, r.bottom);
                        if (visibleRight <= visibleLeft || visibleBottom <= visibleTop) return null;
                        const x = Math.min(Math.max((visibleLeft + visibleRight) / 2, 4), viewportWidth - 4);
                        const y = Math.min(Math.max(visibleTop + Math.min(32, (visibleBottom - visibleTop) / 2), 4), viewportHeight - 4);
                        return {{ x, y, text: el.innerText || el.value || '', disabled: !!el.disabled }};
                    }})()
                    """,
                )

            rect = await wait_for(find_rect, timeout=timeout, interval=0.25, label=f"{page['label']} {testid}")
            for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
                params = {"type": event_type, "x": rect["x"], "y": rect["y"]}
                if event_type != "mouseMoved":
                    params.update({"button": "left", "clickCount": 1})
                await cdp.call("Input.dispatchMouseEvent", params, session_id=page["sid"])
            return rect

        async def visible_testid(page: dict[str, Any], testid: str, *, require_enabled: bool = True) -> dict[str, Any] | None:
            return await eval_page(
                page,
                f"""
                (() => {{
                    const el = document.querySelector('[data-testid="{testid}"]');
                    if (!el) return null;
                    if ({str(require_enabled).lower()} && el.disabled) return null;
                    const r = el.getBoundingClientRect();
                    if (!r.width || !r.height) return null;
                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1365;
                    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 900;
                    const visibleLeft = Math.max(0, r.left);
                    const visibleRight = Math.min(viewportWidth, r.right);
                    const visibleTop = Math.max(0, r.top);
                    const visibleBottom = Math.min(viewportHeight, r.bottom);
                    if (visibleRight <= visibleLeft || visibleBottom <= visibleTop) return null;
                    const x = Math.min(Math.max((visibleLeft + visibleRight) / 2, 4), viewportWidth - 4);
                    const y = Math.min(Math.max(visibleTop + Math.min(32, (visibleBottom - visibleTop) / 2), 4), viewportHeight - 4);
                    return {{
                        x,
                        y,
                        text: el.innerText || el.value || '',
                        disabled: !!el.disabled,
                    }};
                }})()
                """,
            )

        async def fill_testid(page: dict[str, Any], testid: str, value: str, *, timeout: float = 15.0) -> None:
            async def fill_done():
                return await eval_page(
                    page,
                    f"""
                    (() => {{
                        const el = document.querySelector('[data-testid="{testid}"]');
                        if (!el || el.disabled) return null;
                        const r = el.getBoundingClientRect();
                        if (!r.width || !r.height) return null;
                        el.focus();
                        const setter = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value')?.set;
                        if (setter) setter.call(el, {json.dumps(value)});
                        else el.value = {json.dumps(value)};
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return el.value === {json.dumps(value)};
                    }})()
                    """,
                )
            await wait_for(fill_done, timeout=timeout, interval=0.25, label=f"fill {page['label']} {testid}")

        async def click_text_button(page: dict[str, Any], text: str, *, timeout: float = 15.0) -> dict[str, Any]:
            async def find_rect():
                return await eval_page(
                    page,
                    f"""
                    (() => {{
                        const b = [...document.querySelectorAll('button')]
                            .find(btn => !btn.disabled && btn.innerText.includes({json.dumps(text)}));
                        if (!b) return null;
                        const r = b.getBoundingClientRect();
                        if (!r.width || !r.height) return null;
                        return {{ x: r.left + r.width / 2, y: r.top + r.height / 2, text: b.innerText, disabled: !!b.disabled }};
                    }})()
                    """,
                )

            rect = await wait_for(find_rect, timeout=timeout, interval=0.25, label=f"{page['label']} button {text}")
            for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
                params = {"type": event_type, "x": rect["x"], "y": rect["y"]}
                if event_type != "mouseMoved":
                    params.update({"button": "left", "clickCount": 1})
                await cdp.call("Input.dispatchMouseEvent", params, session_id=page["sid"])
            return rect

        async def clear_dialogue_stage(page: dict[str, Any], *, timeout: float = 30.0) -> bool:
            deadline = time.time() + timeout
            clicked = False
            while time.time() < deadline:
                if await visible_testid(page, "adventure-free-action-input", require_enabled=False):
                    return clicked
                visible = await visible_testid(page, "dialogue-stage-continue", require_enabled=False)
                if not visible:
                    await asyncio.sleep(0.25)
                    continue
                await click_testid(page, "dialogue-stage-continue", timeout=2.0)
                clicked = True
                await asyncio.sleep(0.9)
            state = await page_state(page)
            raise TimeoutError(
                f"timed out clearing dialogue stage for {page['label']}; "
                f"url={state.get('url')} testids={state.get('testids')}"
            )

        host_name = data["host_character"]["name"]
        guest_name = data["guest_character"]["name"]

        async def both_room_loaded():
            states = [await page_state(p) for p in pages]
            ok = all(host_name in s["text"] and guest_name in s["text"] for s in states)
            return states if ok else None

        room_states = await wait_for(both_room_loaded, timeout=30, interval=0.5, label="both room pages loaded")

        async def ws_room_two():
            ready = await get_ready(base_api)
            count = ready.get("ws", {}).get("room_connections", {}).get(session_id, 0)
            return ready if count >= 2 else None

        ready_before = await wait_for(ws_room_two, timeout=20, interval=0.5, label="room ws connections >= 2")

        before_path = artifact_dir / f"multiplayer-deep-{session_id[:8]}-host-room.png"
        before_png = (await cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, session_id=host_page["sid"]))["data"]
        before_path.write_bytes(base64.b64decode(before_png))

        rect = await eval_page(
            host_page,
            """
            (() => {
                const buttons = [...document.querySelectorAll('button')];
                const goldButtons = buttons.filter(btn => !btn.disabled && String(btn.className).includes('btn-gold'));
                const b = goldButtons[goldButtons.length - 1];
                if (!b) return null;
                const r = b.getBoundingClientRect();
                return { text: b.innerText, x: r.left + r.width / 2, y: r.top + r.height / 2, disabled: b.disabled, className: String(b.className) };
            })()
            """,
        )
        if not rect:
            raise RuntimeError("start button not found")

        for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
            params = {"type": event_type, "x": rect["x"], "y": rect["y"]}
            if event_type != "mouseMoved":
                params.update({"button": "left", "clickCount": 1})
            await cdp.call("Input.dispatchMouseEvent", params, session_id=host_page["sid"])

        async def both_adventure_loaded():
            states = [await page_state(p) for p in pages]
            ok = all(f"/adventure/{session_id}" in s["url"] for s in states)
            return states if ok else None

        adventure_states = await wait_for(both_adventure_loaded, timeout=35, interval=0.5, label="both adventure pages loaded")

        async def ws_adventure_two():
            ready = await get_ready(base_api)
            count = ready.get("ws", {}).get("room_connections", {}).get(session_id, 0)
            return ready if count >= 2 else None

        ready_after = await wait_for(ws_adventure_two, timeout=25, interval=0.5, label="adventure ws connections >= 2")
        await clear_dialogue_stage(host_page)
        await clear_dialogue_stage(guest_page)

        async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
            room_after_start = await api_request(client, "GET", f"/game/rooms/{session_id}", token=data["host"]["token"])

        if room_after_start.get("current_speaker_user_id") != data["host"]["user_id"]:
            raise RuntimeError(f"expected host speaker after start, got {room_after_start.get('current_speaker_user_id')}")

        await fill_testid(host_page, "adventure-free-action-input", "I inspect the tavern threshold and signal the party to stay alert.")
        await click_testid(host_page, "adventure-free-action-submit")

        async def guest_speaker_room():
            async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
                room = await api_request(client, "GET", f"/game/rooms/{session_id}", token=data["host"]["token"])
            return room if room.get("current_speaker_user_id") == data["guest"]["user_id"] else None

        room_after_host_action = await wait_for(guest_speaker_room, timeout=45, interval=1.0, label="speaker rotates to guest")

        host_action_path = artifact_dir / f"multiplayer-deep-{session_id[:8]}-host-after-action.png"
        host_action_png = (await cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, session_id=host_page["sid"]))["data"]
        host_action_path.write_bytes(base64.b64decode(host_action_png))

        await fill_testid(host_page, "multiplayer-group-action-input", "I keep watch near the door while the guest speaks.")
        await click_testid(host_page, "multiplayer-group-action-submit-ready")

        async def host_intent_ready():
            async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
                room = await api_request(client, "GET", f"/game/rooms/{session_id}", token=data["host"]["token"])
            pending = room.get("pending_actions_by_group", {}).get("main", [])
            readiness = room.get("group_readiness", {}).get("main", {})
            ok = any(item.get("user_id") == data["host"]["user_id"] for item in pending)
            ok = ok and readiness.get(data["host"]["user_id"]) == "ready"
            return room if ok else None

        room_after_group_intent = await wait_for(host_intent_ready, timeout=20, interval=0.5, label="host group intent ready")

        await click_testid(guest_page, "adventure-rest-open")
        await click_testid(guest_page, "rest-short")

        async def active_rest_vote():
            async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
                room = await api_request(client, "GET", f"/game/rooms/{session_id}", token=data["guest"]["token"])
            vote = room.get("rest_vote")
            return room if vote and vote.get("rest_type") == "short" and vote.get("yes_count") == 1 else None

        room_after_rest_vote_created = await wait_for(active_rest_vote, timeout=20, interval=0.5, label="rest vote created")

        await click_testid(host_page, "adventure-rest-open")
        await click_testid(host_page, "rest-vote-yes")

        async def rest_vote_resolved():
            async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
                room = await api_request(client, "GET", f"/game/rooms/{session_id}", token=data["host"]["token"])
            return room if room.get("rest_vote") is None else None

        room_after_rest_vote_resolved = await wait_for(rest_vote_resolved, timeout=20, interval=0.5, label="rest vote resolved")

        rest_vote_path = artifact_dir / f"multiplayer-deep-{session_id[:8]}-rest-vote-resolved.png"
        rest_vote_png = (await cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, session_id=host_page["sid"]))["data"]
        rest_vote_path.write_bytes(base64.b64decode(rest_vote_png))

        host_path = artifact_dir / f"multiplayer-deep-{session_id[:8]}-host-adventure.png"
        guest_path = artifact_dir / f"multiplayer-deep-{session_id[:8]}-guest-adventure.png"
        host_png = (await cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, session_id=host_page["sid"]))["data"]
        guest_png = (await cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, session_id=guest_page["sid"]))["data"]
        host_path.write_bytes(base64.b64decode(host_png))
        guest_path.write_bytes(base64.b64decode(guest_png))

        async with httpx.AsyncClient(base_url=base_api, timeout=30, trust_env=False) as client:
            session_detail = await api_request(client, "GET", f"/game/sessions/{session_id}", token=data["host"]["token"])
            room_detail = await api_request(client, "GET", f"/game/rooms/{session_id}", token=data["host"]["token"])

        output = {
            "session_id": session_id,
            "room_code": data["room_code"],
            "host_user_id": data["host"]["user_id"],
            "guest_user_id": data["guest"]["user_id"],
            "clicked_button": rect,
            "room_states": [{"url": s["url"], "buttons": s["buttons"]} for s in room_states],
            "adventure_states": [
                {"url": s["url"], "text_excerpt": s["text"][:700], "buttons": s["buttons"][:8]}
                for s in adventure_states
            ],
            "ready_before_ws": ready_before.get("ws"),
            "ready_after_ws": ready_after.get("ws"),
            "session_flags": {
                "is_multiplayer": session_detail.get("is_multiplayer"),
                "room_code": session_detail.get("room_code"),
                "combat_active": session_detail.get("combat_active"),
                "current_scene_present": bool(session_detail.get("current_scene")),
                "current_speaker_user_id": (session_detail.get("game_state") or {}).get("multiplayer", {}).get("current_speaker_user_id"),
                "speak_round": (session_detail.get("game_state") or {}).get("multiplayer", {}).get("speak_round"),
            },
            "interaction_flags": {
                "speaker_after_start": room_after_start.get("current_speaker_user_id"),
                "speaker_after_host_action": room_after_host_action.get("current_speaker_user_id"),
                "host_group_intent_count": len(room_after_group_intent.get("pending_actions_by_group", {}).get("main", [])),
                "host_group_readiness": room_after_group_intent.get("group_readiness", {}).get("main", {}).get(data["host"]["user_id"]),
                "rest_vote_created_yes_count": (room_after_rest_vote_created.get("rest_vote") or {}).get("yes_count"),
                "rest_vote_after_resolve": room_after_rest_vote_resolved.get("rest_vote"),
            },
            "room_started": room_detail.get("game_started"),
            "room_members": room_detail.get("members"),
            "screenshots": {
                "host_room": str(before_path.resolve()),
                "host_adventure": str(host_path.resolve()),
                "guest_adventure": str(guest_path.resolve()),
                "host_after_action": str(host_action_path.resolve()),
                "rest_vote_resolved": str(rest_vote_path.resolve()),
            },
            "browser_events": [
                e for e in cdp.events
                if e.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded")
            ],
        }

        for page in pages:
            try:
                await cdp.call("Target.closeTarget", {"targetId": page["target"]})
                await cdp.call("Target.disposeBrowserContext", {"browserContextId": page["ctx"]})
            except Exception:
                pass
        return output


async def main_async(args: argparse.Namespace) -> int:
    data = await prepare_data(args.base_api.rstrip("/"), Path(args.db_path))
    output = await run_browser_flow(args, data)
    print(json.dumps(output, ensure_ascii=True, indent=2))
    if output["ready_after_ws"]["room_connections"].get(output["session_id"], 0) < 2:
        return 1
    if not output["room_started"]:
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a two-user CDP browser multiplayer smoke test.")
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
