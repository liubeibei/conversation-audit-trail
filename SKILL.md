---
name: conversation-audit-trail
description: Turns a requirement or product conversation into an auditable decision-trace document with user quotes, assistant conclusions, confirmation items, and how the user replied. Use whenever the user asks for 痕迹文档, 对话留痕, 需求留痕, 审计文档, decision trace, audit trail, who decided what, or to archive confirmations before implementation. Do not summarize from memory when this skill applies — reconstruct from the session transcript.
---

# Conversation Audit Trail

Produce a **decision-trace document**, not a product spec. The document must answer four questions:

1. What did the user propose?
2. What did the assistant conclude?
3. What did the assistant ask the user to confirm?
4. How did the user reply (or not)?

A later reader must be able to tell **who locked which rule in which turn**.

## When to use

- User asks for 痕迹 / 留痕 / 审计 / decision trace / audit trail
- A multi-turn requirement discussion is about to become an implementation spec
- User wants an auditable record of confirmations before coding

Do **not** use this skill to write the implementation spec itself. If both are requested, write the spec separately and link it from the trace.

## Hard rules

1. Reconstruct from the session **transcript**, not from chat memory.
2. Quote user wording **verbatim**. Do not paraphrase user requirements.
3. Confirmation status has **only four values**. Never invent a fifth. Never promote a default into `用户确认`.
4. Skip system injections (agent type catalogs, hook JSON, `beforeSubmitPrompt` payloads, `<system-reminder>` blocks, tool results, subagent turns, duplicated compacted user turns).
5. Do not start implementation, commit, or push unless the user also asked for that in the same request.
6. Do not copy private business documents into the public example files of this skill.

## Confirmation statuses

| Status | Meaning |
|---|---|
| `用户确认` | User explicitly accepted the point in their own words, or a later team conclusion restates it |
| `用户改写` | User did not say yes/no; a later turn replaced the question with a different rule |
| `默认待确认` | Assistant offered a default; user neither accepted nor rejected it |
| `未回复` | Assistant asked; no later turn addressed it |

If unsure between `默认待确认` and `未回复`: use `未回复` when the assistant asked a direct question; use `默认待确认` when the assistant only stated a default and kept going.

## Workflow

Copy and track:

```
Trace progress:
- [ ] Locate transcript
- [ ] Extract user turns
- [ ] Map assistant conclusions and confirmation items
- [ ] Classify each confirmation
- [ ] Write the trace document
- [ ] Recheck: no default marked 用户确认
```

### 1. Locate the transcript

Prefer the current session `transcript_path` from user/system metadata.

Typical Cursor layout:

`agent-transcripts/<conversation_id>/<conversation_id>.jsonl`

Typical Claude Code layout — one file per session, directory name is the project
path with every non-alphanumeric character replaced by `-` (so `/Users/me/my_app`
becomes `-Users-me-my-app`):

`~/.claude/projects/<escaped-project-path>/<session_id>.jsonl`

To find the current session, pick the most recently modified jsonl in the
directory matching the working directory:

```bash
ls -t ~/.claude/projects/"$(pwd | sed 's#[^a-zA-Z0-9]#-#g')"/*.jsonl | head -1
```

Confirm with the user before reading a session other than the current one.

If a `compaction/` folder exists, use it only to recover missing early turns. The jsonl is the source of truth.

If no transcript is available, stop and say so. Do not invent turns.

### 2. Extract turns

Run the bundled script (UTF-8, Windows-safe). Do not dump JSONL into the chat.
It auto-detects the Cursor and Claude Code layouts; use an absolute path to the
script when the working directory is not the skill folder.

```bash
python3 ~/.claude/skills/conversation-audit-trail/scripts/extract_transcript.py \
  --jsonl "<transcript.jsonl>" --out "<work-dir>/_trace_extract.json"
```

Then read `_trace_extract.json`. It reports the detected `format`, and each user
turn carries a `kind`:

| `kind` | Meaning |
|---|---|
| `prompt` | A real user message — the only kind that can lock a rule |
| `slash_command` | User invoked a command; text is normalized to `/name args` |
| `local_command` | Output of a local command the user ran, not a requirement |

Treat `skip_reason` rows as non-decision turns. Claude Code adds these reasons:
`tool_result` (tool output stored as a user record), `meta` (`isMeta` injection),
`subagent` (`isSidechain` turn), `compact_summary`.

Assistant records sharing one `message.id` are merged into a single turn;
`thinking` and `tool_use` blocks are dropped, so the extract holds only what the
assistant actually said to the user. Internal reasoning is never evidence.

Delete the extract file after the document is written, unless the user wants to keep it.

### 3. Classify

For each **user** turn:

- Record timestamp and verbatim `user_query`
- Summarize the assistant's **decision-facing** conclusion (not tool narration)
- List confirmation items the assistant opened
- Look **forward** to later user turns to mark how each item closed

Also record when a later user turn **overrides** an earlier assistant recommendation. Put those in the "assistant suggestion overwritten" table so the locked plan follows the user, not the first recommendation.

### 4. Write the document

Write a standalone Markdown file the user can hand to product, engineering, or audit.

Default path (change if the user names one):

`docs/<topic>-需求到方案痕迹-<YYYY-MM-DD>.md`

Use [template.md](template.md). Required sections:

0. How to read
1. Original requirement baseline (verbatim)
2. Turn index
3. Per-turn trace (quote / conclusion / asked / reply)
4. Confirmation ledger
5. How user rules overrode the original brief
6. Assistant suggestions the user changed
7. Locked rules as of the last unifying turn
8. Still unconfirmed
9. Things that were explicitly not done
10. Evidence paths

Language: match the user's language (this conversation is Chinese unless they write in English).

### 5. Recheck

Before finishing:

- Every user quote matches the extract
- Every confirmation item has a status from the table above
- No `默认待确认` row is described as locked by the user
- Locked-rules section only contains `用户确认` or `用户改写` items
- Implementation spec, if it exists, is linked — not duplicated

## Output contract

Tell the user:

- File path
- How many decision turns were kept / skipped
- How many items are still `默认待确认` or `未回复`
- That this file is the audit record; the spec (if any) is the build record

## Additional resources

- Document skeleton: [template.md](template.md)
- Short fictional example: [examples.md](examples.md)
