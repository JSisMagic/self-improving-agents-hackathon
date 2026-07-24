# INT-001: External adapters

Status: Archived  
Owner: Team

## Scope

This spec defines stable local boundaries for planned services. It does not
claim that credentials, vendor endpoints, or specific SDK calls currently work.
Those details belong in configuration and implementation evidence.

## Requirements

### INT-001 Common result envelope

Every adapter call shall return a typed payload plus `provider`, `status`,
`mode`, `started_at`, `finished_at`, and a sanitized error when unsuccessful.

### INT-002 Capability probe

At startup or on demand, each adapter shall report whether required
configuration is present and whether a bounded non-destructive probe succeeded.

### INT-003 Pioneer extraction

The Pioneer adapter shall accept source content or URL input and return
schema-valid Event data, or an explicit failure that activates cached
extraction.

### INT-004 Pioneer slow loop

The Pioneer adapter may submit accumulated labeled outcomes for asynchronous
evaluation or training; job status shall be observable and shall not block
recommendation or reranking.

### INT-005 Actian memory

The Actian adapter shall store EventEpisodes and retrieve relevant episodes by
user and event features while preserving episode IDs and relevance provenance.

### INT-006 Band orchestration

The Band adapter shall transport Scout, Analyst, and Coach handoffs without
becoming the implementation of normalization, scoring, or mission validation.

### INT-007 cited.md publication

The cited.md adapter shall submit or publish the exact grounded Markdown
rendering and return a publication result that can be inspected in the demo.

### INT-008 Payment rail

The payment adapter shall target x402 testnet for version 1, isolate all
verification/settlement behavior, and expose explicit demo mode when disabled.

### INT-009 Fixture parity

Each fake adapter shall implement the same local interface and result envelope
as its connected adapter.

### INT-010 Sanitized observability

Adapter logs and statuses shall include correlation IDs and timings but shall
exclude API keys, payment credentials, full provider error bodies, and
unnecessary user feedback.

## Planned interfaces

```python
extract_events(inputs) -> AdapterResult[list[Event]]
store_episode(episode) -> AdapterResult[EpisodeReference]
retrieve_episodes(user_id, event, limit) -> AdapterResult[list[RetrievedEpisode]]
coordinate_agents(context) -> AdapterResult[AgentTranscript]
publish_markdown(markdown) -> AdapterResult[PublicationResult]
authorize_playbook(request) -> AdapterResult[PaymentDecision]
submit_slow_loop_dataset(episodes) -> AdapterResult[JobReference]
```

## Configuration

All provider URLs, model/job IDs, credentials, and testnet payment settings are
environment-backed. `.env.example` may name variables but shall contain no
working secret.
