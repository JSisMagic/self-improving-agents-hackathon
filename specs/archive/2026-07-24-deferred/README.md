# Deferred specification archive

Status: Archived  
Archived: 2026-07-24

These documents preserve accepted design work that is not part of the
time-boxed hackathon release gate. They are non-normative and must not block
implementation or the demo.

## Why these documents moved

- Detailed architecture and capability decomposition duplicated the active
  vertical-slice contract.
- Generalized provider adapters and extended security checks exceeded the
  remaining implementation window.
- The separate audience and memory documents were folded into the active
  product, data, and workflow specs.
- Templates are useful after the hackathon but irrelevant to the current build.

## Reuse rule

To reactivate archived material, move the necessary requirement into an active
owning spec, update the catalog and traceability map, and add an acceptance
check. Do not treat an archived `Status: Archived` requirement as accepted
merely because its stable ID is preserved here.

## Contents

- Audience and detailed architecture: `AUD-001`, `ARC-001`, `ARC-002`
- Detailed memory and capability decomposition: `DAT-002`, `FUN-001..005`
- Separate feedback workflow: `WFL-002`
- Full provider and security contracts: `INT-001`, `SEC-001`
- Extended acceptance checks: `TST-007..012`
- Spec, integration, and ADR templates
