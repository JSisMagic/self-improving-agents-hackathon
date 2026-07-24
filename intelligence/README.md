# Gergana's intelligence module

This module owns event normalization, deterministic baseline scoring, feedback
ingestion, connected Actian or local-fallback episode storage, and
memory-informed reranking.

## Run the learning-loop demo

From the repository root:

```bash
python3 -m intelligence.demo
```

The command loads the three canonical candidates, writes the deliberate mixer
feedback to the configured episode store, and then reranks the same three
candidates. Actian is opt-in; without its environment flag this remains a
temporary local JSON run. The mixer starts first and the workshop overtakes it.

## Refresh product-facing fixtures

```bash
python3 -m intelligence.generate_demo_fixtures
```

Hasan can load `shared/mock_recommendations.json` before integration and switch
to `IntelligenceEngine.rank_events_with_memory()` later. Both return the agreed
Recommendation JSON contract.

The generator also refreshes schema-valid `sample_episode.json` and resets the
legacy `actian_memories.json` fixture to an empty list. Runtime episodes use a
process-local temporary JSON file by default or `EVENT_COPILOT_EPISODES_PATH`
when explicitly configured.

## Connected Actian memory

Install the optional dependencies and start the repository's VectorAI DB
container as described in the root README. Then export
`ACTIAN_VECTORAI_ENABLED=true` before running this module or the product UI.

The connected backend embeds a stable Event fingerprint with
`sentence-transformers/all-MiniLM-L6-v2`, writes the complete EventEpisode as
Actian payload, and searches same-user memories using vector similarity.
Actian selects the relevant episodes; the accepted scoring-version-1 formulas
remain deterministic. Successful connected writes are mirrored to the
session-local JSON store so a later provider error can degrade truthfully.

`ActianMemory` remains a compatibility name for the local JSON backend.
`ActianVectorMemory` is the connected backend, and `create_episode_memory()`
selects the configured path.

## Live Senso-grounded event crawling

`SensoClient.crawl_events(urls)` fetches explicitly supplied public event pages
at call time and extracts schema.org Event JSON-LD into the shared Event
contract. With `SENSO_API_KEY`, it uploads the fetched Markdown snapshot through
Senso's knowledge-base API and waits until compilation completes before
reporting `connected`. Without the key, the crawl can still return current
`data_mode: live` records, but the Senso integration reports `demo_fallback`.

Run it with:

```bash
python3 -m intelligence.senso_client https://example.org/current-event
```

Optional configuration:

- `SENSO_API_KEY`: Senso API credential.
- `SENSO_API_URL`: API base URL; defaults to
  `https://apiv2.senso.ai/api/v1`.

## Other service boundaries

`PioneerClient` reads `PIONEER_API_URL` and `PIONEER_API_KEY` when configured and
falls back to `shared/pioneer_extractions.json`. Pioneer is not used by the
release-gate path.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```
