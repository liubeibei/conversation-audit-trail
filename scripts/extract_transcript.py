#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract decision-facing turns from a Cursor / Claude Code session JSONL.

Two transcript layouts are supported and auto-detected per record:

* Cursor      - top-level ``role``, user text wrapped in ``<user_query>``.
* Claude Code - top-level ``type`` of ``user``/``assistant``, role inside
  ``message``, one API response split across several records that share
  ``message.id``, tool results stored as ``user`` records.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

USER_QUERY = re.compile(r"<user_query>\s*([\s\S]*?)\s*</user_query>")
TIMESTAMP = re.compile(r"<timestamp>(.*?)</timestamp>")
SYSTEM_REMINDER = re.compile(r"<system-reminder>[\s\S]*?</system-reminder>")
LOCAL_STDOUT = re.compile(r"<local-command-stdout>[\s\S]*?</local-command-stdout>")
COMMAND_MESSAGE = re.compile(r"<command-message>[\s\S]*?</command-message>")
COMMAND_NAME = re.compile(r"<command-name>\s*([\s\S]*?)\s*</command-name>")
COMMAND_ARGS = re.compile(r"<command-args>\s*([\s\S]*?)\s*</command-args>")
CAVEAT_LINE = re.compile(r"\ACaveat:[^\n]*\n?")
HOOK_HINTS = (
    "hook_event_name",
    "beforeSubmitPrompt",
    "available_subagent_types",
    "MANDATORY_FORMAT_INSTRUCTION",
)
ASSISTANT_TEXT_LIMIT = 4000


def _texts(message: dict) -> str:
    """Concatenate plain-text blocks. Thinking and tool_use blocks are dropped."""
    content = (message or {}).get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text") or "")
    elif isinstance(content, str):
        parts.append(content)
    return "\n".join(parts)


def _block_types(message: dict) -> set[str]:
    content = (message or {}).get("content")
    if not isinstance(content, list):
        return set()
    return {item.get("type") for item in content if isinstance(item, dict)}


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


def _clean_user_text(text: str) -> tuple[str, str]:
    """Strip injected wrappers. Returns (clean_text, kind)."""
    kind = "prompt"
    text = SYSTEM_REMINDER.sub("", text)
    text = CAVEAT_LINE.sub("", text)
    text = _user_query(text)

    name = COMMAND_NAME.search(text)
    if name:
        args = COMMAND_ARGS.search(text)
        parts = [name.group(1).strip()]
        if args and args.group(1).strip():
            parts.append(args.group(1).strip())
        return (" ".join(parts).strip(), "slash_command")

    text = COMMAND_MESSAGE.sub("", text)
    if LOCAL_STDOUT.search(text):
        text = LOCAL_STDOUT.sub("", text)
        kind = "local_command"
    return (text.strip(), kind)


def _normalize(rec: dict) -> tuple[str, dict] | None:
    """Return (format, normalized) or None when the record carries no turn.

    normalized keys: role, text, timestamp, group, pre_skip
    """
    if rec.get("role") in ("user", "assistant"):
        return (
            "cursor",
            {
                "role": rec["role"],
                "text": _texts(rec.get("message") or {}),
                "timestamp": "",
                "group": None,
                "pre_skip": None,
            },
        )

    kind = rec.get("type")
    if kind not in ("user", "assistant"):
        return None

    message = rec.get("message")
    if not isinstance(message, dict):
        return None

    pre_skip = None
    if rec.get("isSidechain"):
        pre_skip = "subagent"
    elif rec.get("isMeta"):
        pre_skip = "meta"
    elif rec.get("isCompactSummary"):
        pre_skip = "compact_summary"
    elif kind == "user" and "tool_result" in _block_types(message):
        pre_skip = "tool_result"

    return (
        "claude",
        {
            "role": kind,
            "text": _texts(message),
            "timestamp": rec.get("timestamp") or "",
            "group": message.get("id") if kind == "assistant" else rec.get("uuid"),
            "pre_skip": pre_skip,
        },
    )


def extract(path: Path) -> dict:
    users: list[dict] = []
    assistants: list[dict] = []
    skipped: list[dict] = []
    formats: set[str] = set()
    user_n = 0

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

            normalized = _normalize(rec)
            if normalized is None:
                continue
            fmt, turn = normalized
            formats.add(fmt)
            text = turn["text"]

            if turn["pre_skip"]:
                skipped.append(
                    {
                        "line": line_no,
                        "role": turn["role"],
                        "skip_reason": turn["pre_skip"],
                        "preview": text.strip()[:160],
                    }
                )
                continue

            if turn["role"] == "user":
                reason = _should_skip_user(text)
                query, kind = _clean_user_text(text)
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
                        "timestamp": ts_match.group(1) if ts_match else turn["timestamp"],
                        "kind": kind,
                        "text": query,
                    }
                )
            else:
                # One Claude Code API response spans several records sharing
                # message.id; merge them into a single assistant turn.
                group = turn["group"]
                if group is not None and assistants and assistants[-1]["group"] == group:
                    if text.strip():
                        assistants[-1]["text"] = (assistants[-1]["text"] + "\n" + text).strip()
                    continue
                if not text.strip():
                    continue
                assistants.append(
                    {
                        "index": 0,
                        "line": line_no,
                        "timestamp": turn["timestamp"],
                        "group": group,
                        "text": text,
                    }
                )

    for i, item in enumerate(assistants, 1):
        item["index"] = i
        item.pop("group", None)
        item["char_len"] = len(item["text"])
        item["text"] = item["text"][:ASSISTANT_TEXT_LIMIT]

    return {
        "source": str(path),
        "format": "+".join(sorted(formats)) or "unknown",
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
        "format=%s users=%s assistants=%s skipped=%s -> %s"
        % (
            data["format"],
            counts["users"],
            counts["assistants"],
            counts["skipped"],
            out,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
