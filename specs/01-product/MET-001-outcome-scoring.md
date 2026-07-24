# MET-001: Outcome scoring

Status: Accepted  
Owner: Intelligence

## Purpose

Scoring exists to make a change in observed outcomes visibly alter future
recommendations. Version 1 prioritizes determinism and explanation over
mathematical sophistication.

## Requirements

### MET-001 Score range

Networking, knowledge, opportunity, personal fit, friction, actual-success,
confidence, and overall scores shall be bounded and documented; user-facing
scores use `0..100`, while confidence uses `0..1`.

### MET-002 Default predicted outcome weights

The default pre-event outcome score shall use 30% networking, 30% knowledge,
30% opportunity, and 10% personal fit.

### MET-003 Friction treatment

Friction shall be displayed separately and applied as a documented penalty, not
silently mixed into an outcome component.

### MET-004 Versioned calculation

Every recommendation and event episode shall record a `scoring_version`.

### MET-005 Actual event success

Actual event success shall equal 30% networking outcome, 30% knowledge outcome,
30% opportunity outcome, and 10% personal-fit outcome.

### MET-006 Networking evidence

The networking proxy shall incorporate meaningful conversations, contacts
exchanged, and twice the number of meetings booked before normalization.

### MET-007 Deterministic demo normalization

Version 1 shall use deterministic, clamped component normalizers so the same
fixture always produces the same score.

### MET-008 Learning explanation

Any memory-based adjustment shall report the evidence summary, the affected
component, the signed adjustment, and the resulting rank or score delta.

### MET-009 Confidence

Confidence shall decrease when grounding, profile detail, or relevant memory is
missing and shall never be presented as a statistically calibrated probability
unless calibration evidence exists.

## Version 1 formulas

All `clamp` operations bound a value to `0..100`.

```text
predicted_outcome =
  0.30 × networking
+ 0.30 × knowledge
+ 0.30 × opportunity
+ 0.10 × personal_fit

overall = round(clamp(predicted_outcome - 0.15 × friction))
```

The actual-outcome component normalizers are:

```text
networking =
  clamp(10 × (
    meaningful_conversations
    + contacts_exchanged
    + 2 × meetings_booked
  ))

knowledge =
  clamp(15 × questions_answered + 20 × actionable_insights)

opportunity =
  clamp(20 × followups_sent + 40 × opportunities_created)

personal_fit =
  clamp(5 × energy_after + 5 × overall_value)

actual_event_success =
  round(
    0.30 × networking
    + 0.30 × knowledge
    + 0.30 × opportunity
    + 0.10 × personal_fit
  )
```

This formula is a demo contract, not a validated scientific model. A later
formula requires a new scoring version and an ADR if it changes the product
claim.

## Acceptance examples

- With identical inputs and scoring version, results are identical.
- A missing optional feedback field uses the schema default and does not crash.
- The deliberate mixer/workshop fixture changes order after the specified
  episode is recorded and provides an adjustment explanation.

