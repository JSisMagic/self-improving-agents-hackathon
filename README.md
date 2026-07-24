# Event Copilot

Event Copilot is a self-improving event-recommendation agent. It helps a user
choose events for networking, knowledge, and opportunity outcomes; creates a
measurable attendance mission; publishes grounded output; and learns from
post-event feedback so later rankings improve.

The repository is currently in a time-boxed hackathon build. The active specs
define only the vertical slice needed for the demo; detailed post-hackathon
design work is preserved in a non-normative archive.

## Start here

- [Quick two-person build plan](QUICK-PLAN.md)
- [Specification system](specs/README.md)
- [Repository guidance](AGENTS.md)
- [Specification catalog](specs/00-governance/catalog.md)
- [Product requirements](specs/01-product/PRD-001-event-copilot.md)
- [Demo workflow](specs/05-workflows/WFL-001-demo-journey.md)
- [Delivery plan](specs/08-delivery/DEL-001-hackathon-delivery.md)
- [Acceptance checks](specs/08-delivery/TST-001-acceptance-plan.md)
- [Requirement traceability](specs/00-governance/traceability.md)

## Source of truth

Accepted specifications and accepted architecture decision records listed as
active in the catalog are normative. Documents under `specs/archive/` and the
original planning documents remain useful design history, but they do not
override active specs:

- [Challenge statement](task.md)
- [Contract-lock notes](step1.md)
- [Two-person build plan](work-divide.md)

When implementation and an accepted spec disagree, either change the
implementation or accept a spec/ADR change before treating the divergence as
intentional.
