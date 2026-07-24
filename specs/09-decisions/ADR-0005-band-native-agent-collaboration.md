# ADR-0005: Use Band for independent agent collaboration

Status: Accepted  
Date: 2026-07-24  
Deciders: Team

## Context

Scout, Analyst, and Coach currently run as sequential functions inside one
process. Sending those calls through a vendor-shaped wrapper would add latency
without creating meaningful agent collaboration. The useful Band capability is
coordination among independently authenticated agents that retain separate
responsibilities while sharing an inspectable room.

## Decision

Use four Band remote-agent identities in connected mode:

- Event Copilot Coordinator owns the run and recruits the specialists.
- Scout validates source-grounded event candidates.
- Analyst calls the deterministic intelligence boundary and owns ranking.
- Coach independently challenges the recommendation and calls the validated
  mission boundary.

The coordinator creates one room per recommendation run. Work moves through
targeted Band messages in the sequence Coordinator → Scout → Analyst → Coach →
Coordinator. Every message carries the same local `run_id`. The Band SDK
provides WebSocket delivery and processing lifecycle; the Band Agent API
provides room, participant, and outbound-message commands.

The Band message envelope is an integration-private transport contract, not a
seventh shared domain schema. Domain payloads continue to validate against the
six schemas in DAT-001. The existing direct-call path remains the fallback.

## Consequences

- The demo proves real agent-to-agent communication with room and message
  provenance instead of presenting local calls as connected.
- Each agent can move to a separate process or framework without changing the
  ranking or mission contracts.
- Four sibling Band agent IDs under one owner and four agent-specific API keys
  are required for a connected run so the Coordinator can recruit the three
  specialists.
- Missing credentials, provider failures, and timeouts preserve the local
  journey and visibly report `demo_fallback`.
