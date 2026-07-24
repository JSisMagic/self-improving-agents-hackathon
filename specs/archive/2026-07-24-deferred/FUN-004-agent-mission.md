# FUN-004: Agent coordination and Event Mission

Status: Archived  
Owner: Product

## Roles

| Agent | Responsibility | Required output |
| --- | --- | --- |
| Scout | Find and normalize goal-relevant candidates | Valid Event list with sources |
| Analyst | Score candidates using goals and previous outcomes | Ranked Recommendations |
| Coach | Challenge the top choice and prepare execution | Critique plus Event Mission |

## Requirements

### FUN-016 Role separation

Scout, Analyst, and Coach shall have distinct prompts or functions and shall not
silently collapse their responsibilities in connected orchestration mode.

### FUN-017 Visible handoff

The product shall show a concise Scout-to-Analyst and Analyst-to-Coach handoff
with run provenance.

### FUN-018 Recommendation challenge

Coach shall identify at least one weakness, risk, or missing assumption in the
top recommendation before creating the mission.

### FUN-019 Measurable mission

The mission shall validate against `mission.schema.json` and include objectives
that can be compared with post-event feedback.

### FUN-020 Direct-call fallback

If agent orchestration is unavailable, the same role functions shall execute
directly and the UI shall label the mode as `demo_fallback`.

## Mission guidance

Prefer a small number of observable objectives, for example meaningful
conversations, a question to answer, and a follow-up action. Do not promise
access to named people unless a grounded source supports that claim.
