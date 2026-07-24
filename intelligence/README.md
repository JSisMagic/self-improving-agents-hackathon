# Gergana's intelligence module

This module owns event normalization, deterministic baseline scoring, feedback
ingestion, local episode storage, and memory-informed reranking.

## Run the learning-loop demo

From the repository root:

```bash
python3 -m intelligence.demo
```

The command loads the three canonical candidates, writes the deliberate mixer
feedback to a temporary local episode store, and then reranks the same three
candidates. The mixer starts first and the workshop overtakes it.

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

## Deferred-service boundaries

`PioneerClient` reads `PIONEER_API_URL` and `PIONEER_API_KEY` when configured and
falls back to `shared/pioneer_extractions.json`. Pioneer is not used by the
release-gate path. `ActianMemory` is a historical class name for a local JSON
store; it reports `local_fallback` and does not claim an Actian connection.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```
