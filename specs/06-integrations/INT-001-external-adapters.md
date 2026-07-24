# INT-001: Hackathon external actions

Status: Accepted  
Owner: Product

## Scope

Only cited.md publication and an x402 testnet payment boundary are required
external actions for the hackathon build. Pioneer, Actian, Band, generalized
provider probes, and slow-loop jobs are deferred. The core recommendation and
reranking path must remain directly callable with local data.

## Requirements

### INT-001 Minimal result envelope

Each external action shall return `provider`, `status`, `mode`, a payload or
sanitized error, and a timestamp. Supported modes are `connected`,
`demo_fallback`, `disabled`, and `error`.

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

## Minimal interfaces

```python
publish_markdown(markdown) -> PublicationResult
authorize_playbook(request) -> PaymentDecision
```

Provider-specific code stays behind these two functions. The UI consumes only
their normalized results and displays the actual mode.

## Deferred integrations

Pioneer extraction or evaluation, Actian memory, and Band orchestration may be
added only after TST-001 through TST-006 pass. Their earlier generalized
adapter contract is retained in the
[dated archive](../archive/2026-07-24-deferred/INT-001-full-external-adapters.md).
