# Event Copilot specification system

Status: Accepted  
Owner: Team  
Last updated: 2026-07-24

This directory is the authoritative description of the Event Copilot
hackathon vertical slice. Only active documents listed in the catalog are
normative. Detailed design work that is useful later but would slow the current
build is preserved under `archive/`.

## Precedence

Use the following order when sources disagree:

1. A newer accepted ADR that explicitly supersedes an older decision.
2. An active accepted domain spec listed in the catalog.
3. This specification-system overview and governance documents.
4. Proposed or draft specs, which do not override accepted behavior.
5. Archived specs and root planning documents, which are historical inputs.

Implementation does not silently override a spec. Record an intentional change
in the owning spec and, when it changes architecture or product direction, an
ADR.

## Status model

| Status | Meaning |
| --- | --- |
| Proposed | Under discussion; not normative. |
| Accepted | Normative target; implementation may still be incomplete. |
| Implemented | The target exists and has implementation evidence. |
| Verified | Acceptance checks have passed and evidence is recorded. |
| Deprecated | Retained for history and replaced by a named successor. |
| Archived | Preserved for later work; non-normative and not a release gate. |

## Requirement namespaces

| Prefix | Owner |
| --- | --- |
| `PROD` | Product behavior and scope |
| `AUD` | User and audience assumptions |
| `MET` | Scoring and success measurement |
| `ARC` | Architecture and runtime qualities |
| `DAT` | Shared data contracts |
| `FUN` | Functional capabilities |
| `WFL` | End-to-end workflows |
| `INT` | External integration boundaries |
| `SEC` | Security, privacy, and payment safeguards |
| `DEL` | Delivery and team operation |
| `TST` | Verification and acceptance |

An ID is permanent after acceptance. Archived IDs remain reserved, so gaps in
an active namespace are expected and must not be renumbered.

## Change process

1. Find the owning spec in the [catalog](00-governance/catalog.md).
2. During the hackathon, prefer clarifying an existing active requirement over
   adding scope.
3. Add an ADR if the change affects product direction, system boundaries, or an
   earlier decision.
4. Update [traceability](00-governance/traceability.md) and any affected schema.
5. Run `python3 scripts/validate_specs.py`.
6. Implement the smallest vertical slice and attach verification evidence to
   TST-001 through TST-006.

## Definition of ready

A feature is ready only when it directly advances an active acceptance check
and uses the locked JSON contracts. Everything else is deferred by default.

## Definition of done

The hackathon build is done when TST-001 through TST-006 pass, schemas validate,
visible statuses are truthful, and connected cited.md and x402 evidence is
captured. Archived requirements do not block completion.

## Directory map

| Directory | Purpose |
| --- | --- |
| `00-governance/` | Catalog, traceability, terms, and spec rules |
| `01-product/` | Product outcome and deterministic scoring |
| `03-data/` | Canonical data contracts and JSON Schemas |
| `05-workflows/` | One end-to-end demo sequence |
| `06-integrations/` | cited.md and x402 boundaries |
| `07-security/` | Minimum hackathon safeguards |
| `08-delivery/` | Build sequence and verification |
| `09-decisions/` | Architecture decision records |
| `archive/` | Deferred, non-normative design history |
