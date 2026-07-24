# DAT-001: Shared contracts

Status: Accepted  
Owner: Team

## Contract rule

JSON Schemas in [`schemas/`](schemas/) are the machine-readable contract.
The hackathon implementation may use dictionaries or lightweight models as
long as fixtures and boundary outputs validate against them. A contract change
requires both owners to acknowledge it before merge.

## Requirements

### DAT-001 Schema version

Every top-level shared object shall contain `schema_version`; version 1 uses
`"1.0"`.

### DAT-002 Event identity

An Event shall contain a stable `event_id`, title, description, source name,
source URL, start time, location, themes, format, and bounded event
characteristics.

### DAT-003 Event grounding

Live Events shall retain the source URL used to derive their claims; fixtures
shall carry `data_mode: "fixture"`.

### DAT-004 User profile

A UserProfile shall contain a stable `user_id`, goal priorities, desired
outcomes, preferences, and constraints.

### DAT-005 Goal weights

Networking, knowledge, and opportunity priorities shall each be `0..1` and
their sum shall be greater than zero.

### DAT-006 Recommendation

A Recommendation shall contain the Event ID, component scores, overall score,
reasons, confidence, citations, influencing episode IDs, scoring version, and
rank.

### DAT-007 Citation

A Citation shall pair a specific human-readable claim with an absolute source
URL.

### DAT-008 Feedback

EventFeedback shall capture the quantitative fields needed by MET-001 plus
optional free text, user identity, event identity, and submission time.

### DAT-009 Event Mission

An EventMission shall contain measurable objectives, target people or roles,
questions, a follow-up plan, recommendation provenance, and citations.

### DAT-010 Compatibility

Readers shall ignore unknown optional fields within the same major schema
version; removing, renaming, or changing the meaning of a field requires a
major version.

## Minimal learning record

After feedback, the implementation writes one EventEpisode containing the
user, event, pre-feedback recommendation, raw feedback, derived scores,
scoring version, timestamp, and storage mode. Local JSON or in-memory
persistence is sufficient for the hackathon. The record must validate against
`episode.schema.json` before the UI claims learning occurred.

## Machine-readable schemas

- [UserProfile](schemas/profile.schema.json)
- [Event](schemas/event.schema.json)
- [Recommendation](schemas/recommendation.schema.json)
- [EventFeedback](schemas/feedback.schema.json)
- [EventMission](schemas/mission.schema.json)
- [EventEpisode](schemas/episode.schema.json)

## Contract freeze

Implement only the fields required by the six schemas and the visible demo.
Do not generate client libraries, add database migrations, or introduce new
shared object types before TST-001 through TST-006 pass.

## Contract-change protocol

```text
PROPOSED CONTRACT CHANGE:
<field and object>

REASON:
<consumer need>

BREAKING:
yes | no

MIGRATION:
<fixture and reader changes>
```

The proposer updates schema, examples, affected specs, and contract tests in
one change.
