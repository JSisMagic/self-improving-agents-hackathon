# Hasan and Gergana: quick build plan

Goal: demo one complete loop where feedback from a mixer makes a smaller
workshop become the better recommendation.

This is a working checklist. The accepted specs remain the source of truth.

## 1. Start together

- Freeze the six JSON Schemas, three-event fixture, scoring version, and demo
  sequence.
- Agree which event uses a live source and confirm cited.md and x402 testnet
  credentials.
- Do not change `shared/` or a schema unless both agree.

## 2. Build in parallel

### Gergana — intelligence and learning

- Load and validate the profile and three events.
- Rank all events with deterministic scores, reasons, citations, confidence,
  and scoring version.
- Turn feedback into one valid local episode, then rerank.
- Make the workshop overtake the mixer and explain the evidence and score
  change.

### Hasan — product and external actions

- Build one simple screen for the six demo actions.
- Show the Scout → Analyst → Coach handoff and generate a measurable Event
  Mission.
- Keep fixture/live, preview/published, and disabled/connected statuses honest.
- After the local learning loop works, connect cited.md publication and the
  x402 testnet playbook boundary.

## 3. Integrate and finish together

- First pass: profile, ranking, mission, feedback, episode write, and reranking
  all work locally.
- Offline pass: disable credentials and confirm the full local loop still works.
- Connected pass: capture one live event source, remote cited.md result, and
  verifiable x402 testnet response.
- Run all six acceptance checks, rehearse twice without edits, capture evidence,
  then freeze the build.

## Done means

All six checks in `specs/08-delivery/TST-001-acceptance-plan.md` pass. Do not
spend hackathon time on Pioneer, Actian, Band, slow-loop training, extra
features, database work, or visual polish before that.
