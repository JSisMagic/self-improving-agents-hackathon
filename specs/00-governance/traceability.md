# Traceability

Status: Accepted  
Owner: Team

## Planning-source normalization

| Source | Source concern | Owning specs |
| --- | --- | --- |
| [`task.md`](../../task.md) | Autonomous agent continuously evolves toward a goal | PRD-001, WFL-001, TST-006 |
| [`task.md`](../../task.md) | Take real, grounded action | PRD-001, INT-001, SEC-001 |
| [`task.md`](../../task.md) | Publish to cited.md | PRD-001, INT-001, TST-005 |
| [`task.md`](../../task.md) | Monetize with an agent payment rail | PRD-001, INT-001, TST-005 |
| [`step1.md`](../../step1.md) | Event Copilot name and AI/Founders/CTO samples | ADR-0001, PRD-001, DAT-001 |
| [`step1.md`](../../step1.md) | Shared event, recommendation, and feedback contracts | DAT-001 |
| [`step1.md`](../../step1.md) | Outcome score weights and networking proxy | MET-001 |
| [`work-divide.md`](../../work-divide.md) | Stable two-person module ownership | ADR-0002, DEL-001 |
| [`work-divide.md`](../../work-divide.md) | Pioneer and Actian options | Pioneer deferred; Actian governed by ADR-0006, INT-005, and TST-006 |
| [`work-divide.md`](../../work-divide.md) | Band-coordinated Scout, Analyst, and Coach handoffs | ADR-0005, PRD-001, WFL-001, INT-001 |
| [`work-divide.md`](../../work-divide.md) | Outcome evidence changes the next ranking | PRD-001, WFL-001, TST-006 |
| [`work-divide.md`](../../work-divide.md) | Fallbacks and truthful status panel | PRD-001, INT-001, SEC-001, TST-003 |
| [`work-divide.md`](../../work-divide.md) | Demo sequence and freeze rules | WFL-001, DEL-001 |

## Requirement-to-verification map

| Requirement group | Primary verification |
| --- | --- |
| `PROD-001..012` | TST-001 through TST-006 |
| `MET-001..009` | Deterministic scoring check and TST-002, TST-006 |
| `DAT-001..010` | Schema validation exercised by TST-001 through TST-004 |
| `WFL-001..007` | One end-to-end smoke run and TST-006 |
| `INT-001`, `INT-005`, `INT-006`, `INT-007`, `INT-008`, `INT-010` | TST-002, TST-003, TST-005, and TST-006 |
| `SEC-001`, `SEC-003`, `SEC-006`, `SEC-010` | Pre-demo checks and TST-005 |
| `DEL-001..010` | Build checkpoints and rehearsal |
| `TST-001..006` | Recorded acceptance evidence |

## Evidence convention

Add evidence links in `TST-001-acceptance-plan.md` using a commit, test report,
screenshot, captured response, publication URL, or sanitized testnet response.
Archived requirements and TST-007 through TST-012 are reserved for later and
do not need hackathon evidence.
