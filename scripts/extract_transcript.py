#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract decision-facing turns from a Cursor / Claude session JSONL."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

USER_QUERY = re.compile(r"<user_query>\s*([\s\S]*?)\s*</user_query>")
TIMESTAMP = re.compile(r"<timestamp>(.*?)</timestamp>")
HOOK_HINTS = (
    "hook_event_name",
    "beforeSubmitPrompt",
    "available_subagent_types",
    "MANDATORY_FORMAT_INSTRUCTION",
)


def _texts(message: dict) -> str:
    content = (message or {}).get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text") or "")
    elif isinstance(content, str):
        parts.append(content)
    return "\n".join(parts)


def _should_skip_user(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return "empty"
    if stripped.startswith("{") and any(h in stripped for h in HOOK_HINTS):
        return "hook_payload"
    if "<available_subagent_types>" in text:
        return "system_injection"
    if "hook_event_name" in text and "user_query" not in text.lower():
        return "hook_payload"
    return None


def _user_query(text: str) -> str:
    match = USER_QUERY.search(text)
    return (match.group(1).strip() if match else text).strip()


def extract(path: Path) -> dict:
    users: list[dict] = []
    assistants: list[dict] = []
    skipped: list[dict] = []
    user_n = 0
    asst_n = 0

    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                skipped.append({"line": line_no, "skip_reason": "invalid_json"})
                continue

            role = rec.get("role")
            text = _texts(rec.get("message") or {})
            if role == "user":
                reason = _should_skip_user(text)
                query = _user_query(text)
                reason = reason or _should_skip_user(query)
                ts_match = TIMESTAMP.search(text)
                if reason:
                    skipped.append(
                        {
                            "line": line_no,
                            "role": "user",
                            "skip_reason": reason,
                            "preview": query[:160],
                        }
                    )
                    continue
                user_n += 1
                users.append(
                    {
                        "index": user_n,
                        "line": line_no,
                        "timestamp": ts_match.group(1) if ts_match else "",
                        "text": query,
                    }
                )
            elif role == "assistant":
                if not text.strip():
                    continue
                asst_n += 1
                assistants.append(
                    {
                        "index": asst_n,
                        "line": line_no,
                        "char_len": len(text),
                        "text": text[:4000],
                    }
                )

    return {
        "source": str(path),
        "user_turns": users,
        "assistant_turns": assistants,
        "skipped": skipped,
        "counts": {
            "users": len(users),
            "assistants": len(assistants),
            "skipped": len(skipped),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract audit-trail turns from a session JSONL")
    parser.add_argument("--jsonl", required=True, help="Path to session transcript JSONL")
    parser.add_argument("--out", required=True, help="UTF-8 JSON output path")
    args = parser.parse_args()

    src = Path(args.jsonl)
    if not src.is_file():
        print("transcript not found: %s" % src, file=sys.stderr)
        return 2

    data = extract(src)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = data["counts"]
    print(
        "users=%s assistants=%s skipped=%s -> %s"
        % (counts["users"], counts["assistants"], counts["skipped"], out)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
