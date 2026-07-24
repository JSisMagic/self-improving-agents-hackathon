# ADR-0004: Make external integrations gracefully degradable

Status: Accepted  
Date: 2026-07-24  
Deciders: Team

## Context

The required cited.md and x402 actions may have missing credentials, rate
limits, network failures, or unfinished integration work during the demo.

## Decision

Put cited.md and x402 behind the two local interfaces in INT-001. Keep ranking,
mission preview, feedback, and reranking directly callable with local data.
Always expose the actual external-action mode and never present fallback
behavior as connected success.

## Consequences

- The core event-to-learning loop remains demonstrable offline.
- Truthful status is an acceptance requirement.
- Connected evidence is still required before claiming a real provider action.
