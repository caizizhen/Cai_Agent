# Skill extraction (post-task)

You are helping turn a completed task into a **reusable skill draft**.

## Input you will receive

- **Goal**: what the user asked for.
- **Answer**: the assistant’s final answer or summary (may be truncated).
- **Events** (optional): short bullet list of tool / phase events.

## Output rules

Reply with **one JSON object only** (no markdown fences, no commentary). Use UTF-8 string values.

Schema:

```json
{
  "steps": ["ordered reusable step 1", "step 2"],
  "caveats": ["pitfall or constraint 1"],
  "followups": ["optional checklist item for a human to verify"]
}
```

- `steps`: 3–8 concrete actions another run could repeat (commands, files to touch, order matters).
- `caveats`: 0–6 risks, env assumptions, or “gotchas”.
- `followups`: 0–5 human verification items; use `[]` if none.

If information is missing, infer conservatively and say so in `caveats`.
