# TST-001: Acceptance plan

Status: Accepted  
Owner: Team

These six checks are the complete hackathon release gate. Add evidence in the
final column instead of expanding scope during implementation.

| ID | Acceptance scenario | Expected result | Evidence |
| --- | --- | --- | --- |
| TST-001 | Load canonical demo profile and three-event fixture | Profile and all Events validate; goal priorities are visible | [Gergana handoff](../../GERGANA-HANDOFF.md): schema validation and automated suite pass |
| TST-002 | Run initial recommendations | Three ordered Recommendations render with scores, reasons, citations, confidence, version, and data mode; connected evidence shows Coordinator → Scout → Analyst → Coach → Coordinator messages in one Band room | [Gergana handoff](../../GERGANA-HANDOFF.md): deterministic local ranking verified; connected Band evidence pending |
| TST-003 | Disable all external credentials | Full local journey through feedback and reranking succeeds; Actian and Band say `demo_fallback`, and every other integration says `demo_fallback` or `disabled` | [Gergana handoff](../../GERGANA-HANDOFF.md): offline journey verified |
| TST-004 | Select an event and generate a mission | Mission validates and contains measurable objectives, targets, questions, follow-up plan, and citations | Pending |
| TST-005 | Preview/publish and request playbook in fallback and connected profiles | Fallback is labeled; challenge-complete evidence uses a live grounded source and contains a remote cited.md result plus verifiable x402 testnet boundary | Pending |
| TST-006 | Submit deliberate mixer feedback, then rank the next opportunity | The attended mixer is absent from the fresh three-event slate; a newly grounded live event is visibly marked new and shows a memory-adjusted score, influencing episode, source citation, and evidence explanation without a fabricated prior rank; connected evidence includes an Actian write plus same-user cross-event semantic retrieval, while the local structured-similarity path remains deterministic | [Gergana handoff](../../GERGANA-HANDOFF.md): local feedback-to-reranking tests pass; connected Actian evidence pending |

TST-007 through TST-012 retain their stable IDs in the
[deferred archive](../archive/2026-07-24-deferred/TST-001-deferred-checks.md).

## Minimum verification

- Validate the canonical fixtures against all six JSON Schemas.
- Unit-check the deterministic initial scores and the cross-event learning
  adjustment on the new live prospect.
- Run one local smoke journey with external credentials disabled.
- Run one connected Band journey and capture its room ID plus sanitized message
  provenance.
- Run one connected Actian write/retrieval check, including cross-event semantic
  matching and rejection of a different `user_id`.
- Run one final connected journey that captures cited.md and x402 evidence.
- Rehearse the visible demo twice without editing code.

## Evidence rules

Evidence must identify a commit and use one of:

- automated test report;
- captured API response;
- screenshot or screen recording;
- published artifact URL;
- provider job/transaction identifier with secrets removed.

Fallback-mode evidence proves continuity but does not complete TST-005. The
final challenge claim requires the live source, remote cited.md result, and
x402 testnet boundary described in that row.
