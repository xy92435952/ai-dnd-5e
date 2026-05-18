"""Helpers for streaming JSON-shaped LLM responses to the browser."""

from __future__ import annotations

import json
import re
from typing import Any


class JsonStringFieldDeltaExtractor:
    """Incrementally extract decoded text from one JSON string field.

    DM responses are still requested as full JSON for quality and state safety.
    This extractor lets the backend stream only the user-facing narrative while
    the full JSON continues accumulating for final validation and persistence.
    """

    def __init__(self, field_name: str):
        self.field_name = field_name
        self._buffer = ""
        self._scan_pos = 0
        self._value_started = False
        self._escaping = False
        self._unicode_escape: str | None = None
        self.done = False

    def feed(self, chunk: str) -> list[str]:
        if self.done or not chunk:
            return []

        self._buffer += chunk
        if not self._value_started:
            pattern = rf'"{re.escape(self.field_name)}"\s*:\s*"'
            match = re.search(pattern, self._buffer)
            if not match:
                return []
            self._value_started = True
            self._scan_pos = match.end()

        deltas: list[str] = []
        i = self._scan_pos
        while i < len(self._buffer):
            ch = self._buffer[i]
            i += 1

            if self._unicode_escape is not None:
                if re.match(r"[0-9a-fA-F]", ch):
                    self._unicode_escape += ch
                    if len(self._unicode_escape) == 4:
                        deltas.append(chr(int(self._unicode_escape, 16)))
                        self._unicode_escape = None
                    continue
                deltas.append("\\u" + self._unicode_escape + ch)
                self._unicode_escape = None
                continue

            if self._escaping:
                self._escaping = False
                if ch == "u":
                    self._unicode_escape = ""
                    continue
                deltas.append({
                    '"': '"',
                    "\\": "\\",
                    "/": "/",
                    "b": "\b",
                    "f": "\f",
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                }.get(ch, ch))
                continue

            if ch == "\\":
                self._escaping = True
                continue
            if ch == '"':
                self.done = True
                self._scan_pos = i
                break
            deltas.append(ch)

        self._scan_pos = i
        return ["".join(deltas)] if deltas else []


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"
