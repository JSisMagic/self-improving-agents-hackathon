# FUN-001: Event ingestion

Status: Archived  
Owner: Intelligence

## Outcome

Convert source pages or fixture records into valid, deduplicated, grounded Event
objects without making the recommendation path depend on a live extractor.

## Requirements

### FUN-001 Input modes

The ingestor shall accept both live source inputs and cached fixture inputs and
identify the resulting data mode.

### FUN-002 Normalization

Every accepted candidate shall validate against `event.schema.json` before it
reaches ranking.

### FUN-003 Grounding

The ingestor shall preserve source name and URL and shall not infer a factual
claim that cannot be tied to the source or explicitly marked unknown.

### FUN-004 Deduplication

Candidates representing the same event shall be merged or rejected using stable
source identity and normalized title/time/location signals.

### FUN-005 Partial failure

One invalid or unreachable source shall produce a structured item-level error
without discarding valid candidates from the same run.

## Acceptance checks

- The three-event fixture produces three schema-valid Events.
- An invalid record is reported with its source identity and validation reason.
- Repeated fixture input produces the same Event IDs.
- When live extraction fails, cached fixtures are returned as
  `data_mode: "fixture"`.
