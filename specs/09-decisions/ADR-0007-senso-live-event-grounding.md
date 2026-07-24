# ADR-0007: Use Senso for live event-source grounding

Status: Accepted  
Date: 2026-07-24  
Deciders: Team

## Context

The final demo needs at least one current, grounded event source. The operator
also needs an on-demand refresh path rather than relabeling a stored fixture as
live. Senso compiles and indexes supplied sources, while event-page retrieval
remains a distinct crawler responsibility.

## Decision

Add an intelligence-side `SensoClient` boundary that:

1. Fetches explicitly supplied public HTTP(S) event pages at call time.
2. Extracts schema.org Event JSON-LD into the frozen Event contract.
3. Preserves the fetched source URL and labels those records `data_mode: live`.
4. Uploads a bounded Markdown snapshot to Senso and waits for compilation when
   `SENSO_API_KEY` is configured.
5. Reports `connected` only after Senso accepts and compiles every successfully
   crawled source; otherwise it reports `demo_fallback` or `error` truthfully.

The adapter does not discover arbitrary sites, execute page scripts, or expand
the shared Event schema. The canonical three-event fixture remains the
deterministic offline path.

## Consequences

- Live event claims retain their original page URLs.
- Senso can ground later agent queries in the exact fetched snapshot.
- JavaScript-only pages without server-rendered schema.org Event data require a
  future browser or dedicated crawling provider.
- Missing credentials do not block local crawling or the existing learning
  loop, and the result cannot be mistaken for connected Senso ingestion.
