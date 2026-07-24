# Repository guidance

This repository is executing a time-boxed hackathon vertical slice. Before
implementing a feature, read `README.md`, `specs/README.md`, the active owning
spec in `specs/00-governance/catalog.md`, and any relevant ADR.

## Source precedence

Active accepted specs and accepted ADRs listed in the catalog are
authoritative. Documents under `specs/archive/` and the root files `task.md`,
`step1.md`, and `work-divide.md` are historical design inputs. Do not use them
to override or expand the active hackathon release gate.

## Development rules

- Implement against the JSON Schemas in `specs/03-data/schemas/`.
- Preserve stable requirement IDs in code, tests, and evidence where useful.
- Put external services behind the adapter boundary in INT-001.
- Keep the local fallback path working and label its status truthfully.
- Never commit working secrets or claim that fixture/demo behavior is live.
- Propose contract changes before editing shared fields. Update schema,
  fixtures, consumers, specs, and tests together.
- Do not add new capability specs during the hackathon unless a contract
  ambiguity blocks TST-001 through TST-006.
- Pioneer, Actian, Band, slow-loop training, and generalized hardening remain
  deferred until the six active acceptance checks pass.

## Validation

Run:

```bash
python3 scripts/validate_specs.py
```

During implementation, prioritize the six active checks defined by TST-001 and
record demo evidence there.

## Codex agent team

Project-scoped custom agents live in `.codex/agents/`:

- `hasan_lead` coordinates Hasan's scope, integration, and final evidence.
- `ui_flow_worker` owns `product/ui.py` and UI-specific nested assets.
- `agent_mission_worker` owns `product/agents.py` and
  `product/event_mission.py`.
- `actions_worker` owns `product/cited_publisher.py` and
  `product/payment_endpoint.py`.
- `demo_reliability_reviewer` performs a read-only requirements and demo-risk
  review after implementation checkpoints.

Run no more than the three specialist subagents concurrently. The lead retains
integration decisions and waits for all specialists before composing their
results.

Subagents shall not edit `intelligence/`. They shall not edit `shared/`,
schemas, or shared contract fields unless the lead records explicit agreement
from both human owners. While specialists run in parallel, each agent stays
inside its declared write scope and returns proposed cross-boundary changes to
the lead.
