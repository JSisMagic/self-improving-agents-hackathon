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
5. Submit deliberate feedback, write one Actian or labeled local-fallback
   episode, discover a fresh live prospect, and rank a new candidate slate that
   excludes the attended event. The interface must visibly explain how the
   prior outcome affects the new live event.

The core loop may use local fixtures and local persistence for continuity. A
challenge-complete demo also needs a connected Actian write/retrieval, one real
event source, one inspectable cited.md publication, and one inspectable x402
testnet boundary.

## Primary loop

```text
Profile + three grounded events
→ Scout / Analyst / Coach handoff
→ ranked recommendations + Event Mission
→ cited.md publication + x402 playbook boundary
→ deliberate feedback
→ Actian or labeled local-fallback episode write
→ fresh grounded event discovery
→ visible evidence-informed next ranking
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

The connected product shall persist EventEpisodes in Actian VectorAI DB,
retrieve same-user episodes by semantic event similarity, and identify which
episode influenced the post-feedback recommendation. The deterministic local
path shall persist schema-valid episodes in JSON, retain local event-retrieval
metadata, retrieve same-user episodes with a deterministic structured-event
similarity rule, and label that storage as `local_fallback`.

### PROD-006 Coordinated agents

The product shall expose a concise Scout, Analyst, and Coach handoff. In
connected mode, the roles shall be independently authenticated Band agents
coordinating through targeted messages in one inspectable room. In local mode,
the same role functions shall run directly and the interface shall say
`demo_fallback`.

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

After feedback is recorded, the product shall rank a fresh candidate slate
that excludes the attended event and includes at least one newly discovered
live event. It shall show the memory-adjusted score and evidence-based reason
for the new event without inventing a prior rank for a candidate that was not
in the initial slate.

### PROD-012 Non-blocking integrations

Ranking, mission preview, feedback, and reranking shall remain operable with
deterministic local data when cited.md or x402 is unavailable, and the UI shall
label that degraded mode truthfully.

## Canonical demo input

Use a fictional technical founder whose priorities are continuing peer
relationships, autonomous-agent implementation knowledge, and collaborators or
distribution opportunities. The initial three-event fixture must include a
large mixer and a smaller participatory workshop. After deliberate mixer
feedback, the next slate keeps the two unvisited candidates, removes the
attended mixer, and adds a newly grounded live prospect so the demo proves that
experience changes a future decision rather than rescoring the past.

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
