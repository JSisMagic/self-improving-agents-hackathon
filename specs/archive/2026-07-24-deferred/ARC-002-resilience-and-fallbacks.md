# ARC-002: Resilience and fallbacks

Status: Archived  
Owner: Team

## Principle

A degraded service may reduce freshness or realism, but it must not fabricate a
successful integration or prevent the learning-loop demo.

## Requirements

### ARC-007 Deterministic fallback

Every external adapter required by the demo shall have a deterministic local
fallback fixture or direct-call path.

### ARC-008 Bounded calls

External calls shall use configurable timeouts and return a typed failure or
fallback result instead of hanging the user flow.

### ARC-009 Truthful status

The interface shall distinguish at least `connected`, `demo_fallback`,
`disabled`, and `error`; it shall display only states supported by the current
run.

### ARC-010 Demo continuity

Pioneer, Actian, Band, cited.md, or payment failure shall not block local event
loading, initial ranking, mission preview, feedback submission, or reranking.

## Required fallback map

| Integration | Connected behavior | Fallback behavior |
| --- | --- | --- |
| Pioneer | Extract live event data; optionally submit slow-loop evaluation | Load cached normalized event fixtures |
| Actian | Store and retrieve event episodes | Read/write seeded local episode store |
| Band | Orchestrate visible Scout/Analyst/Coach handoffs | Invoke the same agent-role functions directly |
| cited.md | Publish grounded Markdown | Save/render a local Markdown preview |
| Payment rail | Enforce testnet payment for detailed playbook | Return `payment_mode: "demo"` when explicitly disabled |

## Operational rules

- Fallback content carries `data_mode: "fixture"` or
  `integration_status: "demo_fallback"`.
- A live call must never quietly return a fixture labeled as live.
- Secrets or provider error bodies must not be displayed.
- The one-click demo path should allow deliberate fallback simulation.
