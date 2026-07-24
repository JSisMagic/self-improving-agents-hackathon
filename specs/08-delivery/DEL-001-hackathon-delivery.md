# DEL-001: Hackathon delivery

Status: Accepted  
Owner: Team

## Delivery principle

Protect the smallest vertical slice that proves learning: measured outcomes
must visibly and credibly change a later recommendation.

## Requirements

### DEL-001 Contract first

Before implementation continues, both owners shall freeze the six JSON
Schemas, three-event fixture, scoring version, external-action modes, and
WFL-001 demo sequence.

### DEL-002 Stable ownership

Gergana owns `intelligence/`, Hasan owns `product/`, and changes to `shared/`
require explicit agreement.

### DEL-003 Vertical slice first

The first checkpoint shall connect the three-event fixture, ranking, one
product view, selection, mission preview, feedback, one local episode write,
and reranking without external services.

### DEL-004 Checkpoint one

The team shall run TST-001, TST-002, TST-004, and TST-006 before spending time
on optional providers or visual polish.

### DEL-005 Learning gate

The team shall not start cited.md or x402 integration until the local
fresh-slate learning result in TST-006 works.

### DEL-006 External actions

After the learning gate, the team shall connect the smallest inspectable
Actian episode write/retrieval, Band agent room, cited.md publication, and x402
testnet boundary required by TST-002, TST-005, and TST-006.

### DEL-007 Reliability pass

The team shall preserve one deterministic local path from profile load through
reranking and label every fixture, publication, and payment mode truthfully.

### DEL-008 Rehearsal

The complete demo shall run twice without code edits before freeze.

### DEL-009 Freeze

During the final ten minutes, the team shall make no new features, dependency
upgrades, schema changes, or refactors; only demo-blocking fixes are permitted.

### DEL-010 Evidence capture

The final state shall include a Band room or sanitized message trace proving
agent-to-agent routing, plus captured evidence of the Actian memory write and
semantic retrieval, initial and next-opportunity rankings, grounded cited.md
output, and the x402 testnet boundary.

## Remaining-time plan

Use elapsed time from the moment implementation begins:

| Timebox | Team outcome |
| --- | --- |
| T+0–15 min | Freeze fixtures/contracts; both owners can load the same objects |
| T+15–70 min | Parallel ranker/learning work and single-page product shell |
| T+70–90 min | Integrate and pass the local TST-006 learning moment |
| T+90–125 min | Add Actian, cited.md, and x402 testnet evidence in parallel |
| Final 25 min | Run all six checks, rehearse twice, capture evidence, freeze |

If a timebox slips, keep the local learning loop and truthful fallback. Drop
styling, generalized adapters, extra events, and asynchronous training before
dropping challenge-required provider evidence.

## Explicitly deferred

- Pioneer extraction, evaluation, and slow-loop training.
- Generalized provider envelopes, extended negative-path tests, and
  production hardening.
- Any feature or refactor not needed by TST-001 through TST-006.

## Communication format

```text
DONE:
- <completed result>

NEXT:
- <next bounded result>

BLOCKED:
- <blocker or None>

CONTRACT CHANGES:
- <proposal or None>
```
