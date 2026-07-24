# SEC-001: Minimum hackathon safeguards

Status: Accepted  
Owner: Team

These safeguards are release-critical even though the extended production
security plan is deferred.

## Requirements

### SEC-001 Secret handling

Secrets shall be read from environment variables and shall not be committed,
embedded in fixtures, returned to the client, or included in captured evidence.

### SEC-003 Payment default

Payments shall use testnet and default to disabled unless testnet configuration
is explicitly present. Production-value settlement is out of scope.

### SEC-006 Citation integrity

The published renderer shall preserve source URLs from normalized event data
and shall not invent a citation when one is missing.

### SEC-010 Truthful claims

The product shall not label fixture data as live, local previews as published,
demo payment mode as a transaction, or direct function calls as Band
coordination. Band keys and provider response bodies shall not appear in
browser state, room messages, logs, or captured evidence.
Actian episodes shall be filtered by `user_id`; Actian access tokens, model
cache paths, and full provider errors shall not appear in browser state, logs,
or captured evidence.

## Pre-demo checks

- Scan tracked files for accidental secrets.
- Preview the exact content and target before publishing.
- Confirm the payment flow is testnet or explicitly disabled.
- Confirm Band `connected` evidence contains a real room ID and messages
  observed by the coordinator.
- Confirm an Actian `live` episode has inspectable provider evidence and that a
  different `user_id` cannot retrieve it.
- Confirm each visible data, publication, and payment status matches the path
  actually exercised.

The extended provider-error, multi-user, and payment-verification plan remains
available in the
[dated archive](../archive/2026-07-24-deferred/SEC-001-full-security-and-trust.md).
