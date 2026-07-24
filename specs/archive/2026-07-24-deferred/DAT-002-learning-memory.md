# DAT-002: Learning memory

Status: Archived  
Owner: Intelligence

## Purpose

An event episode is the auditable unit of learning. It binds what the system
predicted, what the user reported, what success score was derived, and how that
evidence may affect later events.

## Requirements

### DAT-011 Event episode

An EventEpisode shall identify the user, event, source recommendation,
feedback, actual component scores, actual success, scoring version, timestamps,
and storage mode.

### DAT-012 Immutable observation

Raw feedback and the prediction visible at feedback time shall be retained
unchanged; later derived values shall be versioned rather than overwriting the
observation.

### DAT-013 Retrieval provenance

Memory retrieval shall return episode IDs, similarity or relevance values,
storage mode, and a short reason each episode is relevant.

### DAT-014 User isolation

Episodes shall be retrieved for the same `user_id` unless a future accepted spec
defines anonymized aggregate learning.

## Machine-readable schema

- [EventEpisode](../../03-data/schemas/episode.schema.json)

## Retrieval contract

```python
retrieve_similar_experiences(
    user_id: str,
    event: Event,
    limit: int = 5,
) -> list[RetrievedEpisode]
```

Results are ordered most relevant first. A missing store returns an explicit
fallback result, not an unlabeled empty history.

## Seeded demo memory

The standard fixture set contains eight episodes. At least one shows that a
large mixer generated conversations but no continuing follow-ups, while a small
participatory workshop generated fewer contacts and more continuing
relationships. Seeded evidence must be labeled as fixture data.
