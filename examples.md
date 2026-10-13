# Example (fictional)

This example is generic on purpose. Do not paste private project traces into this file.

## Trigger

```text
把这次从需求到方案的确认过程整理成可审计的痕迹文档。
```

## Extract (abbreviated)

User #1: "先评估把退货入口做到商家后台有没有致命阻断。原型只参考。"

Assistant: No code blocker. Asked Q1-1: is refund approval in shop admin or platform admin?

User #2: "商家后台只建单，审批仍在平台。"

Assistant: Feasible. Opened Q2-1: delay merchant dashboard merge?

User #3: "统一当前逻辑，先出痕迹文档。"

## Ledger result

| ID | Item | Status | Why |
|---|---|---|---|
| Q1-1 | Who approves refunds | 用户改写 | User #2 replaced the open question with "shop creates, platform approves" |
| Q2-1 | Delay dashboard merge | 默认待确认 | Assistant suggested delay; user never said yes or no |
| Q3-1 | Start coding | 未回复 | Nobody authorized implementation |

## Locked rules (only confirmed / rewritten)

- Shop creates the refund ticket; platform approves.
- Prototype is reference-only.

## Must remain open

- Dashboard merge (Q2-1) stays `默认待确认`.
- Coding stays `未回复`.

If a later spec lists "dashboard merge is deferred" as a user decision, the trace is wrong.
