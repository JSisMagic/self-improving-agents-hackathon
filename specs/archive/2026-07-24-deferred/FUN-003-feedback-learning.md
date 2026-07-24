# FUN-003: Feedback learning loop

Status: Archived  
Owner: Intelligence

## Outcome

Turn feedback into an auditable event episode and visibly improve the next
ranking during the same user journey.

## Requirements

### FUN-011 Feedback validation

The learning loop shall reject feedback that violates
`feedback.schema.json` before calculating outcomes or writing memory.

### FUN-012 Outcome derivation

The learning loop shall calculate actual component scores and event success
using the recorded MET-001 scoring version.

### FUN-013 Episode write

The learning loop shall store or locally persist one DAT-002 episode containing
the original prediction, raw feedback, derived outcomes, and provenance.

### FUN-014 Immediate rerank

After a successful episode write, the system shall retrieve memory and rerank
candidate events without requiring a model-training job.

### FUN-015 Learning delta

The product shall compare the pre-feedback and post-feedback rankings and show
which events moved, by how much, and why.

## Deliberate demonstration

The canonical fixture begins with a large mixer above a small workshop. An
episode showing conversations but no continuing relationships causes the mixer
to fall, while evidence from participatory workshops causes the workshop to
rise. Exact fixture values live with implementation, but the expected ordering
is asserted by TST-006.

## Failure behavior

- Invalid feedback does not mutate memory.
- A live memory failure uses the labeled local store and still reranks.
- A write failure in both stores leaves the original ranking intact and reports
  the failure; it must not claim learning occurred.
