# ADR-0006: Use Actian for connected semantic episode memory

Status: Accepted  
Date: 2026-07-24  
Deciders: Team

## Context

Event Copilot already proves its fast learning loop with a schema-valid local
EventEpisode. The final recommendation now evaluates a fresh slate rather than
rescoring an attended event, so both connected and fallback paths need
cross-event retrieval. The Actian challenge requires VectorAI DB to be a core
part of the running system. Persisting a copy without using vector retrieval
would not improve the product claim or demonstrate why a vector database is
appropriate.

Actian VectorAI DB stores and searches vectors but does not create embeddings.
The connected path therefore needs one stable local embedding model while the
existing dependency-free JSON path remains available for the release gate and
demo recovery.

## Decision

In connected mode, use Actian VectorAI DB as the EventEpisode storage and
semantic retrieval backend:

- embed a deterministic fingerprint of Event title, description, themes,
  format, location, interaction level, knowledge depth, and crowd size;
- store the complete schema-valid EventEpisode as point payload while retaining
  its stable `episode_id`;
- filter every retrieval by `user_id` and `schema_version`;
- return the top same-user semantic matches plus episode IDs and relevance
  evidence;
- let the accepted scoring-version-1 calculation consume the selected
  episodes without weighting outcome values by vector similarity; and
- mirror successful connected writes into the session-local JSON store so a
  later provider failure can degrade without losing the visible learning loop.

The dependency-free fallback stores the EventEpisode unchanged and writes
retrieval-only event metadata beside the episode JSON. It selects same-user
episodes with a deterministic structured similarity score over themes, format,
location, interaction level, knowledge depth, and crowd size. This fallback is
for repeatable local continuity; it remains labeled `local_fallback` and is not
presented as vector or semantic-provider evidence.

Actian is opt-in through environment configuration. Missing configuration,
dependencies, model files, health, or provider operations activate the labeled
local fallback. An episode uses `storage_mode: "live"` only after a successful
Actian write. Provider errors expose only a sanitized class or status, never
credentials or full response bodies.

## Consequences

- Vector retrieval becomes part of the connected feedback-to-reranking path,
  rather than an unused persistence sidecar.
- Similar past events may influence a new event even when their Event IDs
  differ.
- The attended event is excluded from the final prospective slate, so the
  visible learning claim applies to a future decision.
- The six shared JSON Schemas and scoring version remain unchanged.
- TST-003 continues to prove deterministic operation without Actian.
- Connected Actian evidence is required before the project claims VectorAI DB
  integration; fallback evidence proves continuity only.
- Similarity-weighted outcome scoring remains a future scoring-version change.
