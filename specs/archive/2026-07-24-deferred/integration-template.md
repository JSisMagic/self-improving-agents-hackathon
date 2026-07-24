# INT-NNN: <Provider or integration>

Status: Archived  
Owner: <owner>  
Parent: INT-001

## Purpose

<What capability this provider supplies without redefining core product logic.>

## Local interface

```python
<method>(...) -> AdapterResult[...]
```

## Configuration

| Variable | Required | Secret | Safe default |
| --- | --- | --- | --- |
| `<NAME>` | yes/no | yes/no | `<value or none>` |

## Connected behavior

<Request, response mapping, idempotency, timeout, and retry behavior.>

## Fallback behavior

<Fixture or local implementation with the same interface.>

## Status mapping

<How provider states map to connected, demo_fallback, disabled, and error.>

## Security constraints

<Allowed actions, secret handling, publication/payment gates, and data scope.>

## Contract tests

- <The same assertion against fake and connected implementations.>
