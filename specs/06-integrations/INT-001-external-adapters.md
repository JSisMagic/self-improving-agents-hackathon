# INT-001: Hackathon external actions

Status: Accepted  
Owner: Product

## Scope

Actian semantic episode memory, Band coordination, cited.md publication, and an
x402 testnet payment boundary are the connected integrations for the hackathon
build. Senso live-source ingestion is an optional candidate-grounding input
added by ADR-0007; it does not replace either challenge action. Pioneer,
generalized provider probes, and slow-loop jobs are deferred. The core
recommendation and reranking path must remain directly callable with local data.

## Requirements

### INT-001 Minimal result envelope

Each external action shall return `provider`, `status`, `mode`, a payload or
sanitized error, and a timestamp. Supported modes are `connected`,
`demo_fallback`, `disabled`, and `error`.

### INT-005 Actian semantic episode memory

The connected memory backend shall store each schema-valid EventEpisode in
Actian VectorAI DB as payload beside an embedding of stable Event features. It
shall retrieve the most relevant episodes by vector similarity while applying
server-side `user_id` and `schema_version` filters. Retrieval provenance shall
retain episode IDs, relevance values, provider, storage mode, and a concise
reason.

The accepted scoring-version-1 calculation shall use Actian to select evidence
but shall not weight outcomes by similarity. Missing configuration,
dependencies, embedding model, health, timeout, or provider success shall use
the local JSON backend with deterministic structured-event similarity and
report `demo_fallback`. Provider-private retrieval metadata may be stored
beside the unchanged EventEpisode JSON. `storage_mode: "live"` may be claimed
only after a successful Actian upsert.

### INT-006 Band agent collaboration

Four independently authenticated Band agents shall participate in each
connected recommendation run: an Event Copilot coordinator plus Scout,
Analyst, and Coach specialists. The coordinator shall create a Band room,
recruit the three specialists, and start the run by mentioning Scout. Each
specialist shall receive only messages that mention it and shall hand work to
the next role through a Band message with the same `run_id`.

Band supplies persistent agent identity, room membership, targeted routing,
WebSocket delivery, processing state, and the inspectable room transcript. It
shall not implement event validation, scoring, critique rules, or mission
validation; connected agents shall call the same local role functions as the
fallback path.

A connected result shall expose the Band room ID plus non-secret message
provenance. A run may be labeled `connected` only after the Coach result is
received by the coordinator through Band. Missing configuration, SDK failure,
timeout, or provider error shall activate the direct-call fallback and shall
not be presented as Band success.

### INT-007 cited.md publication

The cited.md boundary shall publish the exact grounded Event Mission Markdown
and return an inspectable remote identifier or URL. A local preview is allowed
for continuity but shall not be presented as a publication.

### INT-008 Payment rail

The payment boundary shall use x402 testnet for the detailed playbook and
return an inspectable payment-required or verification response. Demo mode may
keep the interface usable but shall not be presented as a transaction.

### INT-010 Sanitized configuration and errors

Credentials shall come from environment variables. Results, logs, screenshots,
and errors shall omit keys, payment tokens, provider request bodies, and other
secret values.

### INT-011 Senso live event grounding

When live source URLs are supplied, the intelligence boundary shall fetch each
page at request time, extract schema.org Event data into the frozen Event
contract, and preserve the page URL as grounding. When `SENSO_API_KEY` is
configured, the fetched source snapshot shall be uploaded and compiled through
Senso before the adapter reports `connected`. Without Senso credentials, a
successful direct crawl may be returned as `demo_fallback`, but shall not be
presented as connected Senso behavior.

## Minimal interfaces

```python
create_episode_memory(fallback_path) -> EpisodeMemory
record(episode, event) -> None
retrieve_similar(user_id, event, limit) -> list[EventEpisode]
coordinate_agents(profile, events, run_id) -> AgentCoordinationResult
publish_markdown(markdown) -> PublicationResult
authorize_playbook(request) -> PaymentDecision
```

Provider-specific code stays behind these boundaries. The UI consumes only
their normalized results and displays the actual mode.

The optional live candidate input uses:

```python
crawl_events(urls) -> EventCrawlResult
```

Senso remains the grounded context and ingestion layer. Fetching and parsing the
event pages is a separate bounded crawler step, matching Senso's documented
source-ingestion model.

## Deferred integrations

Pioneer extraction or evaluation may be added only after TST-001 through
TST-006 pass. Its earlier generalized adapter contract is retained in the
[dated archive](../archive/2026-07-24-deferred/INT-001-full-external-adapters.md).
