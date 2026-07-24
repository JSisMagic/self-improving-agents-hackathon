# Gergana's intelligence module

This module owns event normalization, baseline scoring, historical outcome
retrieval, feedback ingestion, and memory-informed reranking.

## Run the learning-loop demo

From the repository root:

```bash
python3 -m intelligence.demo
```

The expected story is visible in the output: the large AI mixer starts first,
then drops after memory reveals weak follow-through; the hands-on agent workshop
moves to first because similar workshops produced meetings, insights, and
opportunities.

## Refresh product-facing fixtures

```bash
python3 -m intelligence.seed_episodes
python3 -m intelligence.generate_demo_fixtures
```

Hasan can load `shared/mock_recommendations.json` before integration and switch
to `IntelligenceEngine.rank_events_with_memory()` later. Both return the agreed
Recommendation JSON contract.

## Live-service boundaries

`PioneerClient` reads `PIONEER_API_URL` and `PIONEER_API_KEY` when configured and
falls back to `shared/pioneer_extractions.json`. `ActianMemory` currently reports
`demo fallback` and stores eight seeded experiences in
`shared/actian_memories.json`; its persistence boundary can be swapped for the
live Actian service without changing scoring or UI code.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```
