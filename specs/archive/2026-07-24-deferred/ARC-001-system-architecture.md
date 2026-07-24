# ARC-001: System architecture

Status: Archived  
Owner: Team

## Context

The system must demonstrate autonomous action and learning while remaining
reliable inside a short hackathon demo. External vendors are replaceable
adapters; the shared contracts and learning behavior are the durable core.

## Logical architecture

```text
Sources / fixtures
        │
        ▼
Event ingestion ──► normalized Event[]
        │
        ▼
Scout ──► memory retrieval ──► Analyst/scorer ──► Recommendation[]
                                             │
                                             ▼
                                    Coach / Event Mission
                                             │
                                ┌────────────┴────────────┐
                                ▼                         ▼
                         cited.md adapter          payment adapter
                                │                         │
                                └────────────┬────────────┘
                                             ▼
                                      User feedback
                                             │
                                             ▼
                                  episode store / rerank
```

## Requirements

### ARC-001 Contract boundary

All modules shall exchange the versioned data objects owned by DAT-001 and
DAT-002 rather than importing another module's internal models.

### ARC-002 Core separability

Event normalization, ranking, feedback recording, and reranking shall be
callable without the UI, agent-orchestration vendor, publishing vendor, or
payment vendor.

### ARC-003 Adapter boundary

Pioneer, Actian, Band, cited.md, and payment-rail calls shall be isolated behind
interfaces owned by INT-001.

### ARC-004 Pipeline orchestration

An integration layer shall compose capabilities into WFL-001 and WFL-002 and
shall not contain vendor-specific scoring or persistence logic.

### ARC-005 Ownership boundary

`intelligence/` shall own ingestion, scoring, memory, and learning;
`product/` shall own user flow, agent presentation, mission, publishing, and
payment; `shared/` shall own contracts and fixtures.

### ARC-006 Observable provenance

Each pipeline run shall preserve a `run_id`, data mode, scoring version,
citations, influencing episode IDs, and integration statuses.

## Planned module map

```text
shared/
  contracts.py
  schemas/
  sample_profile.json
  sample_events.json
  sample_feedback.json
intelligence/
  event_extractor.py
  scorer.py
  memory.py
  learning_loop.py
product/
  agents.py
  event_mission.py
  cited_publisher.py
  payment_endpoint.py
  ui.py
integration/
  pipeline.py
  demo_scenario.py
tests/
```

The filenames are recommended, not themselves a public API. The module
boundaries and shared contracts are normative.

## Core interfaces

```python
normalize_events(source_inputs) -> list[Event]
rank_events(profile, events, memories=None) -> list[Recommendation]
retrieve_similar_experiences(user_id, event) -> list[EventEpisode]
record_event_outcome(user_id, event, feedback) -> EventEpisode
create_event_mission(profile, event, recommendation) -> EventMission
publish_mission(mission) -> PublicationResult
get_playbook(event_id, payment_context) -> PlaybookResult
```
