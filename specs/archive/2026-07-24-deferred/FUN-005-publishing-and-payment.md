# FUN-005: Publishing and paid playbook

Status: Archived  
Owner: Product

## Outcome

Take two real, inspectable actions: publish a grounded Event Mission and expose
a more detailed success playbook through an agent-compatible payment boundary.

## Requirements

### FUN-021 Markdown rendering

The product shall render the Event Mission as readable Markdown with a Sources
section that preserves claim-level URLs.

### FUN-022 Publication result

The cited.md adapter shall return a structured result containing status, local
content or path, remote identifier or URL when available, timestamp, and error
information when applicable.

### FUN-023 Free recommendation endpoint

`GET /api/recommendations` shall expose event title, component scores, short
explanation, source, and data mode without requiring payment.

### FUN-024 Detailed playbook endpoint

`GET /api/events/{event_id}/playbook` shall expose target people or roles,
questions, objectives, and follow-up strategy behind the payment adapter when
payments are enabled.

### FUN-025 Explicit payment mode

When `PAYMENTS_ENABLED=false`, the detailed endpoint may return demo content
with `payment_mode: "demo"`; it shall not imply that a payment was requested,
verified, or settled.

## Response boundary

Connected payment responses distinguish `payment_required`, `verified`,
`settled`, and `failed`. Demo mode is a separate state, not a successful
transaction.

Publishing or payment failure shall not block mission preview, feedback, or
reranking.

## Challenge-complete gate

Fallback modes are reliability features, not substitutes for the required
external actions. Final submission evidence must include a remote cited.md
publication identifier or URL and an x402 testnet response that demonstrates
the paid boundary. A completed testnet settlement is preferred when the
provider flow supports it safely.
