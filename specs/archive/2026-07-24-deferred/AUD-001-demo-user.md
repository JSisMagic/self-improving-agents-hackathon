# AUD-001: Demo user and event set

Status: Archived  
Owner: Product

## Intent

The demo uses a fictional, reproducible profile. It must not depend on a team
member's private data or live browsing history.

## Requirements

### AUD-001 Fictional profile

The shared demo profile shall use a stable fictional `user_id`, a short role
description, explicit goals, preferences, and constraints.

### AUD-002 Goal priorities

The profile shall express networking, knowledge, and opportunity priorities on
a documented numeric scale and include desired outcome text.

### AUD-003 Event coverage

The demo fixture set shall contain at least one AI event, one Founders event,
and one CTO event, with enough variation to produce a meaningful ranking.

### AUD-004 Learning contrast

Fixtures shall include a large mixer and a smaller participatory workshop so
seeded or submitted outcomes can credibly reverse their order.

## Canonical demo profile

This is the content contract, not the final serialization:

| Field | Demo value |
| --- | --- |
| `user_id` | `demo_user_001` |
| Role | Technical founder building AI products |
| Networking goal | Build continuing peer relationships, not maximize contacts |
| Knowledge goal | Learn implementation patterns for autonomous agents |
| Opportunity goal | Find collaborators, customers, or distribution partners |
| Preferred format | Participatory workshops and small technical sessions |
| Location | San Francisco |
| Cost ceiling | Configurable; default fixture permits free events |

The exact numeric weights belong in `shared/sample_profile.json` once the
implementation begins and must satisfy MET-001.

## Fixture guidance

Use 8–10 candidates in normal demos and always retain a smaller three-event
fixture for fast contract tests. Do not use invented citations in a mode labeled
as live; fixture URLs must be visibly marked as sample data.
