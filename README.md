# conversation-audit-trail

Cursor / Claude skill that turns a multi-turn **requirement conversation** into an auditable decision-trace document.

The document answers:

1. What the user proposed (verbatim)
2. What the assistant concluded
3. What the assistant asked the user to confirm
4. How the user replied — or that they did not

Defaults proposed by the assistant are **never** written as user-approved decisions.

## Why

Product discussions with an agent produce locked rules, open questions, and silent defaults. A later spec often collapses those into “we decided…”. This skill keeps the trail so audit, product, and engineering can see who locked which rule in which turn.

## Install

### Cursor (personal)

Copy or clone this folder to:

```text
~/.cursor/skills/conversation-audit-trail/
```

On Windows:

```powershell
git clone <your-fork-or-this-repo> "$env:USERPROFILE\.cursor\skills\conversation-audit-trail"
```

Restart Cursor or start a new agent chat so the skill is picked up.

### Claude Code

```text
~/.claude/skills/conversation-audit-trail/
```

Same `SKILL.md` works in both.

## Trigger examples

- 把这次从需求到方案整理成痕迹文档
- 出一份可审计的对话留痕
- 记录哪些点我确认了、哪些还是默认
- Write an audit trail of who decided what before we implement

## What the agent should produce

A standalone Markdown file, usually:

```text
docs/<topic>-需求到方案痕迹-<YYYY-MM-DD>.md
```

Required sections are in [`template.md`](template.md). Confirmation statuses are only:

| Status | Meaning |
|---|---|
| `用户确认` | User explicitly accepted |
| `用户改写` | A later user turn replaced the question |
| `默认待确认` | Assistant default; user did not accept or reject |
| `未回复` | Assistant asked; no later turn addressed it |

## Extract script

The agent should not dump raw JSONL into the chat. Use:

```bash
python scripts/extract_transcript.py --jsonl "<session.jsonl>" --out "_trace_extract.json"
```

The transcript layout is auto-detected per record, so the same script handles both hosts.

Cursor transcripts typically live at:

```text
agent-transcripts/<conversation_id>/<conversation_id>.jsonl
```

Claude Code transcripts live at `~/.claude/projects/<escaped-project-path>/<session_id>.jsonl`, where the directory name is the project path with every non-alphanumeric character replaced by `-`:

```bash
ls -t ~/.claude/projects/"$(pwd | sed 's#[^a-zA-Z0-9]#-#g')"/*.jsonl | head -1
```

Claude Code specifics the extractor handles: role lives in `type` rather than a top-level `role`; one assistant response is split across records sharing `message.id` and gets merged; `thinking` and `tool_use` blocks are dropped; tool results, `isMeta` injections, `isSidechain` subagent turns, and `<system-reminder>` blocks are skipped or stripped.

Requires Python 3.9+ (stdlib only).

## Publish your own copy

This machine may not have `gh` installed. From the repo root:

```powershell
git init
git add .
git commit -m "Add conversation-audit-trail skill for requirement decision traces."
gh repo create conversation-audit-trail --public --source=. --remote=origin --push
```

Without `gh`, create an empty public repository on GitHub, then:

```powershell
git remote add origin https://github.com/<you>/conversation-audit-trail.git
git branch -M main
git push -u origin main
```

Suggested GitHub topics: `cursor-skill`, `claude-skill`, `audit-trail`, `decision-log`.

## License

MIT. See [LICENSE](LICENSE).
