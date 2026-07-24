# TST-001: Deferred acceptance checks

Status: Archived  
Archived: 2026-07-24  
Reason: Useful hardening work that is not a hackathon release gate.

These stable IDs are preserved for post-hackathon hardening.

| ID | Deferred acceptance scenario | Expected result |
| --- | --- | --- |
| TST-007 | Calculate actual success for a fixed feedback fixture | Output matches MET-001 exactly and is stable across runs |
| TST-008 | Validate shared fixtures and cross-object IDs | All JSON validates; references resolve; wrong IDs and ranges fail |
| TST-009 | Simulate each adapter failing independently | Core journey continues and status matches the actual path taken |
| TST-010 | Submit invalid feedback | Validation errors are actionable; no live or fallback episode is written |
| TST-011 | Attempt cross-user memory retrieval | No episodes for another user are returned |
| TST-012 | Scan tracked content and exercise extended error paths | No secrets leak; payment and publishing claims remain truthful |
