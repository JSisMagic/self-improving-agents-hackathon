# ADR-0002: Use contract-first stable module ownership

Status: Accepted  
Date: 2026-07-24  
Deciders: Team

## Context

Two people must build in parallel inside a short window. Splitting by ad hoc
tasks would create overlapping files and late integration risk.

## Decision

Freeze the six shared JSON Schemas first. Gergana owns intelligence and
learning; Hasan owns the product shell and external actions. Changes to shared
contracts require acknowledgment from both owners. Integration work happens at
the checkpoints in DEL-001.

## Consequences

- Each owner can develop against deterministic mocks.
- Contract changes carry schema, fixture, consumer, and test updates together.
- Shared and integration files require coordination, but most implementation
  remains parallel.
