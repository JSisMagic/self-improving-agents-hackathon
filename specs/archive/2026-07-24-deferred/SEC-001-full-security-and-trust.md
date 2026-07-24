# SEC-001: Security and trust

Status: Archived  
Owner: Team

## Requirements

### SEC-001 Secret handling

Secrets shall be read from environment variables or an approved secret store
and shall not be committed, embedded in fixtures, or returned to the client.

### SEC-002 Example configuration

The implementation shall provide `.env.example` with placeholders for every
required setting and safe defaults for fallbacks and payments.

### SEC-003 Payment default

Payments shall default to disabled unless testnet configuration is explicitly
present; production-value settlement is out of scope.

### SEC-004 Payment verification

A connected paid response shall be released only after the configured adapter
verifies the payment condition; client-supplied success flags are not trusted.

### SEC-005 Publishing confirmation

The interface shall preview the exact grounded content and identify the target
before any connected publication action.

### SEC-006 Citation integrity

The renderer shall preserve citation URLs from normalized data and shall not
invent sources to fill a missing citation.

### SEC-007 Data minimization

The product shall collect only profile and feedback fields required by the
accepted specs and shall avoid private contact details in demo fixtures.

### SEC-008 User isolation

Memory queries and writes shall include `user_id`; cross-user retrieval is
forbidden in version 1.

### SEC-009 Safe errors

User-visible errors shall omit secrets, stack traces, provider request bodies,
and payment tokens while retaining an operator-usable correlation ID.

### SEC-010 Truthful claims

The product shall not label fixtures as live, local previews as published,
submitted jobs as trained models, or demo payment mode as a transaction.

## Required negative-path checks

- Repository secret scan finds no credential-shaped values in tracked files.
- A forged payment-success input does not unlock connected paid output.
- Missing citations prevent connected publishing but still allow a local
  clearly marked draft for debugging.
- A request for another `user_id` returns no episodes.
