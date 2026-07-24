# WFL-002: Feedback-to-reranking sequence

Status: Archived  
Owner: Team

## Requirements

### WFL-008 Capture before state

The workflow shall retain pre-feedback ranks, scores, run ID, scoring version,
and relevant memory IDs.

### WFL-009 Validate and derive

The workflow shall validate feedback and derive actual outcome scores before
writing an episode.

### WFL-010 Persist and retrieve

The workflow shall persist the episode, retrieve relevant episodes for the same
user, and identify whether connected or fallback storage was used.

### WFL-011 Produce after state

The workflow shall rerun the same candidate set and profile using the same
scoring version unless the demo explicitly demonstrates a version change.

### WFL-012 Explain delta

The workflow shall display before/after ranks and scores plus an evidence
summary that names the observed behavior responsible for the adjustment.

## Sequence

```text
Recommendation run A
→ feedback validation
→ actual-success calculation
→ immutable episode write
→ relevant-episode retrieval
→ recommendation run B
→ delta comparison
→ explanation
```

## Atomicity rule

Run B may occur only after a successful live or fallback episode write. If no
write succeeds, the system reports the error and does not claim self-improvement.
