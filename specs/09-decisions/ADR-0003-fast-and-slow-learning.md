# ADR-0003: Separate fast and slow learning loops

Status: Accepted  
Date: 2026-07-24  
Deciders: Team

## Context

The challenge requires visible self-evolution. A model training or evaluation
job is too slow and unreliable to prove improvement synchronously.

## Decision

Use a locally stored event episode for the hackathon loop: record feedback,
derive outcomes, adjust scores, and rerank immediately. Pioneer evaluation or
training remains a possible asynchronous slow loop after the six active
acceptance checks pass; it is not part of the hackathon release gate.

## Consequences

- The ranking change can be demonstrated deterministically.
- No training-job integration is required for the time-boxed build.
- Scoring versions preserve comparisons when a slow-loop result is adopted.
