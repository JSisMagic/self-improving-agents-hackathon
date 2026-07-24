# FUN-002: Recommendation and explanation

Status: Archived  
Owner: Intelligence

## Outcome

Produce deterministic, goal-aligned recommendations that distinguish baseline
predictions from memory-informed adjustments.

## Requirements

### FUN-006 Baseline scoring

The scorer shall produce all MET-001 components for each valid candidate using
the profile and event alone.

### FUN-007 Memory-informed scoring

When relevant episodes exist, the scorer shall apply bounded adjustments and
record the influencing episode IDs.

### FUN-008 Stable ordering

Recommendations shall be ordered by descending overall score, then descending
confidence, then stable Event ID as the deterministic tie-breaker.

### FUN-009 Top recommendations

The standard product view shall return the top three recommendations when at
least three valid candidates exist.

### FUN-010 Explainability

Each recommendation shall include goal-specific reasons, citations, confidence,
scoring version, and any memory adjustment explanation required by MET-008.

## Acceptance checks

- The same profile, candidates, episodes, and scoring version yield byte-stable
  ranking values.
- Each displayed reason refers to a score component or named memory adjustment.
- A run with no memory still returns valid baseline recommendations.
- Missing optional Event data does not crash ranking.
