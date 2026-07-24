# PRD-001: Event Copilot

Status: Accepted  
Owner: Team

## Problem

Event discovery products optimize for attention and registration. They do not
show whether attendance produced useful relationships, knowledge, or
opportunities, and they do not learn from the attendee's measured outcomes.

## Product outcome

Event Copilot recommends which event a user should attend, prepares a measurable
mission, takes grounded publish/payment actions, captures the result, and uses
that evidence to improve the next recommendation.

## Hackathon scope

The build is one deterministic vertical slice, not a general event platform:

1. Load one fictional profile and three events.
2. Rank and explain the events.
3. Select one event and create a measurable Event Mission.
4. Publish that grounded mission to cited.md and expose its detailed playbook
   through an x402 testnet boundary.
5. Submit deliberate feedback, write one local episode, rerank the same events,
   and visibly explain why the workshop overtakes the mixer.

The core loop may use local fixtures and local persistence. A challenge-complete
demo still needs one real event source, one inspectable cited.md publication,
and one inspectable x402 testnet boundary.

## Primary loop

```text
Profile + three grounded events
→ Scout / Analyst / Coach handoff
→ ranked recommendations + Event Mission
→ cited.md publication + x402 playbook boundary
→ deliberate feedback
→ local episode write
→ visible before/after reranking
```

## Requirements

### PROD-001 Goal capture

The product shall accept a user profile with networking, knowledge, and
opportunity goals before ranking events.

### PROD-002 Diverse candidates

The product shall load at least three candidates spanning the AI, Founders, and
CTO demo categories. At least one final-demo candidate shall come from a live
grounded source; the remaining candidates may be labeled fixtures.

### PROD-003 Grounded recommendations

Every displayed recommendation shall preserve at least one source citation and
explain its relevance to the user's goals.

### PROD-004 Outcome-based ranking

The product shall rank events using predicted networking, knowledge,
opportunity, personal-fit, and friction scores.

### PROD-005 Experience memory

The product shall locally persist and retrieve event episodes and identify
which episode influenced the post-feedback recommendation.

### PROD-006 Coordinated agents

The product shall expose a concise Scout, Analyst, and Coach handoff. Distinct
functions or prompts are sufficient; an orchestration vendor is not required.

### PROD-007 Measurable mission

The product shall generate an Event Mission with concrete attendance and
follow-up objectives for a selected event.

### PROD-008 Grounded publication

The product shall render the Event Mission as citation-bearing Markdown and
publish it through the cited.md adapter for a challenge-complete submission.
A local preview preserves development continuity but is not publication
evidence.

### PROD-009 Monetized output

The product shall expose a detailed success playbook through a selected agent
payment rail for a challenge-complete submission, with a non-deceptive demo
mode when payments are disabled during development.

### PROD-010 Feedback capture

The product shall capture the feedback fields in DAT-001 after an attended or
simulated event.

### PROD-011 Visible self-improvement

After feedback is recorded, the product shall rerun ranking and show the score
or rank delta plus the evidence-based reason for the change.

### PROD-012 Non-blocking integrations

Ranking, mission preview, feedback, and reranking shall remain operable with
deterministic local data when cited.md or x402 is unavailable, and the UI shall
label that degraded mode truthfully.

## Canonical demo input

Use a fictional technical founder whose priorities are continuing peer
relationships, autonomous-agent implementation knowledge, and collaborators or
distribution opportunities. The three-event fixture must include a large mixer
and a smaller participatory workshop so deliberate feedback can reverse their
initial ordering.

## Non-goals for the hackathon version

- General-purpose event ticketing, registration, or calendar management.
- Automated attendance or impersonation of the user.
- Autonomous production spending or irreversible payment settlement.
- A mathematically optimized or statistically validated scoring model.
- Training a large model in the synchronous demo path.
- Multi-tenant production identity, billing, and compliance.

## Release gate

The hackathon build is accepted when TST-001 through TST-006 pass in one
rehearsed journey. TST-005 must include one live grounded source, an inspectable
cited.md publication, and an x402 testnet response. Preview and demo-payment
modes preserve continuity but do not satisfy the external-action requirement.

Architecture decomposition, generalized providers, asynchronous model
training, multi-user hardening, and broader tests are explicitly deferred in
the [dated archive](../archive/2026-07-24-deferred/README.md).
